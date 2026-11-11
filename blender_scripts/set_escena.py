"""Escenarios y objetos con los que el personaje interactúa (lo usa escena_toma.py).

Escenarios («escenario» de la toma):
  estudio (fondo HDRI + piso), habitacion, pasillo, ascensor, oficina, hospital, exterior.
  La sala se construye alrededor del recorrido del personaje Y de la cámara (la cámara nunca queda fuera),
  con texturas PBR de Poly Haven, luces de techo (cálidas o fluorescentes) y muebles contra las paredes,
  lejos del recorrido. Si la toma tiene una puerta, esa pared lleva el hueco de la puerta.

Interacciones («objetos»): cada una dice qué objeto, con qué mano y en qué tramo de cuadros. El cuadro
de contacto se detecta en la animación (dónde llega la mano):
  puerta    la manija queda donde llega la mano y la hoja gira siguiendo la mano (abrir/cerrar).
  tocar     puerta cerrada en el punto donde la mano golpea.
  boton     tablero en la pared donde la mano presiona.
  agarrar   el objeto espera donde la mano lo toma (sobre una mesa si está alto), luego la sigue.
  soltar    el objeto empieza en la mano y queda donde la mano baja más.
  lanzar    sigue la mano y sale volando (con gravedad) cuando la mano va más rápido.
  mano      (telefono, taza, libro…) en la mano todo el tramo.
  caja      con las dos manos (entre ambas).
  sentarse  silla bajo la cadera en el cuadro más bajo, a la altura justa y de espaldas al respaldo.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

# ───────────────────────── utilidades ─────────────────────────

MANOS = {
    "R": (["mixamorig:RightHand"], ["DEF-Hand.R"], ["DEF-Wrist.R"]),
    "L": (["mixamorig:LeftHand"], ["DEF-Hand.L"], ["DEF-Wrist.L"]),
}
CADERA = (["mixamorig:Hips"], ["DEF-Pelvis"], ["DEF-Hips"])


def hueso(rig, grupos):
    for g in grupos:
        if all(n in rig.pose.bones for n in g):
            return rig.pose.bones[g[0]]
    raise SystemExit(f"No encuentro el hueso {grupos[0][0]} (ni equivalentes) en {rig.name}")


def palma(rig, pb) -> Vector:
    """Centro de la palma: un poco más allá de la muñeca, hacia los dedos."""
    return rig.matrix_world @ (pb.head + (pb.tail - pb.head) * 0.75)


def trayectorias(rig, f0: int, f1: int, manos=("R", "L")) -> dict:
    esc = bpy.context.scene
    hm = {m: hueso(rig, MANOS[m]) for m in manos}
    hc = hueso(rig, CADERA)
    t = {"cadera": {}, "R": {}, "L": {}, "matriz_R": {}, "matriz_L": {}}
    for f in range(f0, f1 + 1):
        esc.frame_set(f)
        t["cadera"][f] = (rig.matrix_world @ hc.head).copy()
        for m, pb in hm.items():
            t[m][f] = palma(rig, pb)
            t[f"matriz_{m}"][f] = (rig.matrix_world @ pb.matrix).copy()
    return t


def adelante_de(rig, tray: dict, f: int) -> Vector:
    v = rig.matrix_world.to_3x3() @ Vector((0, -1, 0))  # los rigs miran a -Y
    v.z = 0
    return v.normalized() if v.length > 1e-4 else Vector((0, -1, 0))


def velocidad(tr: dict, f: int) -> float:
    a, b = tr.get(f - 1, tr[f]), tr.get(f + 1, tr[f])
    return (b - a).length * 15.0  # m/s (30 fps, diferencia centrada)


def material_pbr(nombre: str, tex: dict, tam_m: float = 1.0, color=(0.8, 0.8, 0.8)) -> bpy.types.Material:
    """Material PBR con proyección de caja en coordenadas del objeto (misma escala en todas las caras)."""
    mat = bpy.data.materials.new(nombre)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(x for x in n if x.type == "BSDF_PRINCIPLED")
    if not tex or not tex.get("color"):
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = 0.6
        return mat
    coord = n.new("ShaderNodeTexCoord")
    mapeo = n.new("ShaderNodeMapping")
    mapeo.inputs["Scale"].default_value = (1 / tam_m, 1 / tam_m, 1 / tam_m)
    l.new(coord.outputs["Object"], mapeo.inputs["Vector"])

    def imagen(ruta, datos=False):
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(ruta, check_existing=True)
        t.projection, t.projection_blend = "BOX", 0.25
        if datos:
            t.image.colorspace_settings.name = "Non-Color"
        l.new(mapeo.outputs["Vector"], t.inputs["Vector"])
        return t

    l.new(imagen(tex["color"]).outputs["Color"], bsdf.inputs["Base Color"])
    if tex.get("rugosidad"):
        l.new(imagen(tex["rugosidad"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if tex.get("normal"):
        nm = n.new("ShaderNodeNormalMap")
        l.new(imagen(tex["normal"], True).outputs["Color"], nm.inputs["Color"])
        l.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def material_color(nombre: str, color, rugosidad=0.5, metal=0.0, emision=0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(nombre)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = next(x for x in mat.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rugosidad
    bsdf.inputs["Metallic"].default_value = metal
    if emision:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emision
    return mat


def caja(nombre: str, dim, centro, mat=None, coleccion=None) -> bpy.types.Object:
    """Caja con dimensiones reales (sin escala de objeto: las texturas de proyección no se estiran)."""
    import bmesh

    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * dim[0], v.co.y * dim[1], v.co.z * dim[2]))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nombre, me)
    ob.location = centro
    if mat:
        me.materials.append(mat)
    (coleccion or bpy.context.scene.collection).objects.link(ob)
    return ob


def biselar(ob, ancho=0.01):
    m = ob.modifiers.new("Bisel", "BEVEL")
    m.width, m.segments = ancho, 2
    return ob


def emparentar(hijos, nombre: str) -> bpy.types.Object:
    # Sin actualizar la escena, matrix_world de un objeto recién creado es la identidad (medido en GPU por
    # Antigravity: la puerta quedaba hundida a media altura y la pantalla del teléfono oculta).
    bpy.context.view_layer.update()
    raiz = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(raiz)
    for h in hijos:
        m = h.matrix_world.copy()
        h.parent = raiz
        h.matrix_world = m
    bpy.context.view_layer.update()
    return raiz


# ───────────────────────── objetos procedurales ─────────────────────────

def crear_telefono():
    cuerpo = biselar(caja("telefono", (0.072, 0.009, 0.15), (0, 0, 0.075),
                          material_color("telefono_negro", (0.02, 0.02, 0.025), 0.3, 0.2)), 0.006)
    pantalla = caja("telefono_pantalla", (0.064, 0.001, 0.138), (0, -0.0047, 0.075),
                    material_color("pantalla", (0.25, 0.45, 0.9), 0.1, 0, 1.5))
    return emparentar([cuerpo, pantalla], "Telefono")


def crear_taza():
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.042, depth=0.1, location=(0, 0, 0.05))
    taza = bpy.context.object
    taza.name = "taza"
    taza.data.materials.append(material_color("ceramica", (0.92, 0.9, 0.86), 0.25))
    s = taza.modifiers.new("Grosor", "SOLIDIFY")
    s.thickness = 0.005
    bpy.ops.mesh.primitive_torus_add(major_radius=0.026, minor_radius=0.007, location=(-0.05, 0, 0.055),
                                     rotation=(math.pi / 2, 0, 0))
    asa = bpy.context.object
    asa.data.materials.append(taza.data.materials[0])
    return emparentar([taza, asa], "Taza")


def crear_libro():
    tapa = biselar(caja("libro_tapa", (0.16, 0.03, 0.23), (0, 0, 0.115),
                        material_color("tapa", (0.55, 0.12, 0.1), 0.6)), 0.004)
    hojas = caja("libro_hojas", (0.152, 0.026, 0.222), (0.006, 0, 0.115), material_color("papel", (0.93, 0.9, 0.82), 0.8))
    return emparentar([tapa, hojas], "Libro")


def crear_boton():
    placa = biselar(caja("boton_placa", (0.12, 0.02, 0.2), (0, 0, 0), material_color("acero", (0.75, 0.76, 0.78), 0.3, 1.0)), 0.004)
    b = caja("boton", (0.04, 0.012, 0.04), (0, -0.014, 0.03), material_color("luz_boton", (1.0, 0.6, 0.1), 0.3, 0, 3))
    return emparentar([placa, b], "Boton")


def crear_puerta(ancho=0.9, alto=2.05, color=(0.55, 0.38, 0.24)):
    """Hoja de puerta con el origen en la bisagra (gira alrededor de Z), manija a 0.82 m de la bisagra.
    Ejes locales: X a lo ancho (hacia la manija), Y grosor, Z alto."""
    hoja = biselar(caja("puerta_hoja", (ancho, 0.045, alto), (ancho / 2, 0, alto / 2),
                        material_color("madera_puerta", color, 0.45)), 0.006)
    metal = material_color("manija", (0.8, 0.8, 0.82), 0.25, 1.0)
    manija_a = biselar(caja("manija_frente", (0.12, 0.02, 0.022), (ancho - 0.12, -0.06, 1.0), metal), 0.004)
    manija_b = biselar(caja("manija_atras", (0.12, 0.02, 0.022), (ancho - 0.12, 0.06, 1.0), metal), 0.004)
    raiz = emparentar([hoja, manija_a, manija_b], "Puerta")
    raiz["manija_local"] = (ancho - 0.1, -0.06, 1.0)
    return raiz


PROCEDURALES = {"telefono": crear_telefono, "taza": crear_taza, "libro": crear_libro, "boton": crear_boton,
                "puerta": crear_puerta}


def importar_modelo(ruta: str, nombre: str) -> bpy.types.Object:
    """glTF de Poly Haven → un solo objeto raíz con el origen abajo al centro."""
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ruta)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    mallas = [o for o in nuevos if o.type == "MESH"]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in mallas for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    base = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    raiz = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(raiz)
    for o in nuevos:
        if o.parent is None:
            m = o.matrix_world.copy()
            o.parent = raiz
            o.matrix_world = Matrix.Translation(-base) @ m
    bpy.context.view_layer.update()
    raiz["tam"] = tuple(mx - mn)
    return raiz


def crear_objeto(item: dict) -> bpy.types.Object:
    if item.get("procedural") in PROCEDURALES:
        return PROCEDURALES[item["procedural"]]()
    if item.get("ruta"):
        ob = importar_modelo(item["ruta"], item.get("tipo", "objeto"))
        if item.get("alto_m"):  # objetos de mano: tamaño realista
            alto = max(1e-3, ob["tam"][2])
            ob.scale = [item["alto_m"] / alto] * 3
        return ob
    raise SystemExit(f"Objeto sin modelo: {item}")


def mallas_de(raiz) -> list:
    return [o for o in raiz.children_recursive if o.type == "MESH"] + ([raiz] if raiz.type == "MESH" else [])


def altura_asiento(raiz) -> float:
    """Altura del asiento: rayo de arriba hacia abajo en el centro del mueble (el respaldo queda atrás)."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tam = Vector(raiz["tam"]) * raiz.scale[0]
    origen = raiz.matrix_world.to_translation() + Vector((0, 0, tam.z + 0.5))
    mejor = None
    for dx, dy in ((0, 0), (0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05)):
        hit, pos, *_ = bpy.context.scene.ray_cast(dg, origen + Vector((dx, dy, 0)), Vector((0, 0, -1)))
        if hit:
            mejor = pos.z if mejor is None else min(mejor, pos.z)
    return mejor if mejor is not None else tam.z * 0.5


def respaldo_claro(raiz) -> Vector | None:
    """Dirección del respaldo si el mueble tiene uno claro (sillón, sofá, cama, banca); None si no (mesa)."""
    pts = [o.matrix_world @ v.co for o in mallas_de(raiz) for v in o.data.vertices]
    if not pts:
        return None
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    altos = [p for p in pts if p.z > zmin + (zmax - zmin) * 0.75]
    c = sum(pts, Vector()) / len(pts)
    d = sum(((p - c) for p in altos), Vector()) / len(altos)
    d.z = 0
    ancho = max(max(p.x for p in pts) - min(p.x for p in pts), max(p.y for p in pts) - min(p.y for p in pts))
    return d.normalized() if d.length > 0.08 * max(ancho, 0.1) else None


def lado_respaldo(raiz) -> Vector:
    """Dirección (horizontal) hacia el respaldo: donde está la parte alta del mueble."""
    pts = [o.matrix_world @ v.co for o in mallas_de(raiz) for v in o.data.vertices]
    if not pts:
        return Vector((0, 1, 0))
    zmax = max(p.z for p in pts)
    altos = [p for p in pts if p.z > zmax * 0.75]
    c = raiz.matrix_world.to_translation()
    d = sum(((p - c) for p in altos), Vector()) / len(altos)
    d.z = 0
    return d.normalized() if d.length > 0.02 else Vector((0, 1, 0))


# ───────────────────────── interacciones ─────────────────────────

def poner_matriz(ob, m: Matrix, f: int):
    ob.matrix_world = m
    ob.keyframe_insert("location", frame=f)
    ob.keyframe_insert("rotation_euler", frame=f)
    ob.keyframe_insert("scale", frame=f)


def cuadro_contacto(tray, mano: str, d0: int, d1: int, modo: str, rig) -> int:
    """Cuadro en que la mano llega al objeto, buscado en la primera parte del tramo."""
    fin = d0 + max(1, int((d1 - d0) * 0.8))
    cands = [f for f in range(d0, fin + 1) if f in tray[mano]]
    if modo == "bajo":     # recoger del piso o de una mesa: la mano más baja y casi quieta
        return min(cands, key=lambda f: tray[mano][f].z + 0.15 * velocidad(tray[mano], f))
    adelante = adelante_de(rig, tray, d0)
    # alcanzar algo al frente: la mano más adelantada respecto a la cadera y casi quieta
    return max(cands, key=lambda f: (tray[mano][f] - tray["cadera"][f]).dot(adelante) - 0.1 * velocidad(tray[mano], f))


def seguir_mano(ob, tray, mano: str, desde: int, hasta: int, ancla: int):
    """El objeto sigue a la mano entre «desde» y «hasta», con el desfase que tenía en el cuadro «ancla»."""
    desfase = tray[f"matriz_{mano}"][ancla].inverted() @ ob.matrix_world
    for f in range(desde, hasta + 1):
        poner_matriz(ob, tray[f"matriz_{mano}"][f] @ desfase, f)


def interaccion(rig, item: dict, tray: dict, f0: int, f1: int, info: list, partes_puerta: list):
    tipo = item["interaccion"]
    mano = item.get("mano", "R")
    d0, d1 = max(f0, int(item.get("desde", f0))), min(f1, int(item.get("hasta", f1)))
    adelante = adelante_de(rig, tray, d0)
    registro = {"tipo": tipo, "objeto": item.get("tipo"), "desde": d0, "hasta": d1}

    if tipo in ("puerta", "tocar"):
        c = cuadro_contacto(tray, mano, d0, d1, "frente", rig)
        hm = tray[mano][c]
        lado = Vector((adelante.y, -adelante.x, 0))  # a la derecha del personaje
        s = 1 if (hm - tray["cadera"][c]).dot(lado) >= 0 else -1
        puerta = crear_objeto({"procedural": "puerta"})
        # La hoja queda perpendicular a la dirección del personaje, con la manija donde llega la mano.
        # De la bisagra hacia la manija: hacia el lado de la mano. Así el hueco queda delante del cuerpo y
        # el personaje puede pasar por la puerta después de abrirla.
        eje_x = (lado * s).normalized()
        normal = -adelante                   # cara de la puerta que mira al personaje
        rot = Matrix((eje_x, Vector((0, 0, 1)).cross(eje_x), Vector((0, 0, 1)))).transposed().to_4x4()
        manija_local = Vector(puerta["manija_local"])
        bisagra = hm + adelante * 0.06 - eje_x * manija_local.x
        bisagra.z = 0.0
        puerta.matrix_world = Matrix.Translation(bisagra) @ rot
        z_base = puerta.rotation_euler.z  # sin atan2 aparte: evita el salto +π/−π (giro de 360° antes de tocarla)
        puerta.keyframe_insert("rotation_euler", frame=f0)
        partes_puerta.append({"bisagra": bisagra.copy(), "eje": eje_x.copy(), "normal": normal.copy(),
                              "ancho": 0.9, "alto": 2.05})
        registro.update({"contacto": c, "manija_z": round(hm.z, 2)})
        if tipo == "puerta":
            puerta.keyframe_insert("rotation_euler", frame=max(f0, c - 1))  # cerrada hasta que la toca
            # La hoja gira siguiendo a la mano desde el contacto hasta que la suelta (o se aleja).
            ang_prev, signo = 0.0, 0
            r0 = (hm - bisagra)
            r0.z = 0
            for f in range(c, d1 + 1):
                r = tray[mano][f] - bisagra
                r.z = 0
                ang = math.atan2(r0.cross(r).z, r0.dot(r))
                if signo == 0 and abs(ang) > math.radians(4):
                    signo = 1 if ang > 0 else -1
                ang = max(ang_prev, abs(ang) if signo and ang * signo > 0 else ang_prev)
                if (tray[mano][f] - (bisagra + Matrix.Rotation(ang * (signo or 1), 3, "Z") @ (hm - bisagra))).length > 0.25:
                    break  # soltó la manija
                ang_prev = min(ang, math.radians(100))
                puerta.rotation_euler.z = z_base + ang_prev * (signo or 1)
                puerta.keyframe_insert("rotation_euler", frame=f)
            # termina de abrirse sola si quedó más de medio abierta
            if ang_prev > math.radians(15) and f < d1:
                puerta.rotation_euler.z = z_base + math.radians(95) * (signo or 1)
                puerta.keyframe_insert("rotation_euler", frame=min(d1, f + 12))
            registro["angulo_max"] = round(math.degrees(ang_prev), 1)
        info.append(registro)
        return

    if tipo == "boton":
        c = cuadro_contacto(tray, mano, d0, d1, "frente", rig)
        ob = crear_objeto({"procedural": "boton"})
        rot = Matrix.Rotation(math.atan2(adelante.y, adelante.x) + math.pi / 2, 4, "Z")
        ob.matrix_world = Matrix.Translation(tray[mano][c] + adelante * 0.03) @ rot
        registro["contacto"] = c
        info.append(registro)
        return

    ob = crear_objeto(item)
    if tipo in ("mano", "caja"):
        if tipo == "caja":  # entre las dos manos
            if item.get("escala"):
                ob.scale = [float(item["escala"])] * 3
                bpy.context.view_layer.update()
            p = (tray["R"][d0] + tray["L"][d0]) / 2
            ob.matrix_world = Matrix.Translation(p - Vector((0, 0, Vector(ob["tam"]).z * ob.scale[0] / 2)))
        else:
            rot_mano = tray[f"matriz_{mano}"][d0].to_quaternion().to_matrix().to_4x4()
            # «desfase» (m, en los ejes de la mano) saca el objeto de la palma para que no quede tapado.
            # Está calibrado para la mano R (−X sale de la palma); en la L el eje palmar es +X.
            v_desf = Vector(item.get("desfase", (0.0, 0.0, 0.0)))
            if mano == "L":
                v_desf.x = -v_desf.x
            desfase = rot_mano.to_3x3() @ v_desf
            giro_mano = Matrix.Rotation(math.pi, 4, "Z") if mano == "L" else Matrix.Identity(4)
            esc_m = Matrix.Scale(float(item["escala"]), 4) if item.get("escala") else Matrix.Identity(4)
            ob.matrix_world = Matrix.Translation(tray[mano][d0] + desfase) @ rot_mano @ giro_mano @ esc_m
        # el objeto acompaña a la mano toda la toma (no solo durante el tramo)
        seguir_mano(ob, tray, mano if tipo == "mano" else "R", f0, f1, d0)
    elif tipo == "agarrar":
        c = cuadro_contacto(tray, mano, d0, d1, "bajo", rig)
        p = tray[mano][c].copy()
        ob.matrix_world = Matrix.Translation(p - Vector((0, 0, 0.03)))
        poner_matriz(ob, ob.matrix_world.copy(), f0)
        if p.z > 0.35:  # alto: una mesa debajo, con la cubierta justo bajo el objeto
            alto_mesa = p.z - 0.06
            biselar(caja("mesa_apoyo", (0.7, 0.5, alto_mesa), Vector((p.x, p.y, alto_mesa / 2)),
                         material_color("mesa_madera", (0.45, 0.3, 0.2), 0.5)), 0.01)
        poner_matriz(ob, ob.matrix_world.copy(), c)
        seguir_mano(ob, tray, mano, c, d1, c)
        registro["contacto"] = c
    elif tipo in ("soltar", "lanzar"):
        ob.matrix_world = Matrix.Translation(tray[mano][d0])
        if tipo == "soltar":
            c = cuadro_contacto(tray, mano, d0, d1, "bajo", rig)
        else:
            c = max(range(d0, d1 + 1), key=lambda f: velocidad(tray[mano], f))
        seguir_mano(ob, tray, mano, d0, c, d0)
        if tipo == "lanzar":  # sale con la velocidad de la mano y cae
            v = (tray[mano][min(c + 1, d1)] - tray[mano][max(c - 1, d0)]) * 15.0
            p0 = ob.matrix_world.to_translation()
            m = ob.matrix_world.copy()
            for k, f in enumerate(range(c + 1, f1 + 1)):
                t = (k + 1) / 30.0
                p = p0 + v * t + Vector((0, 0, -4.9 * t * t))
                if p.z <= 0.02:
                    p.z = 0.02
                    v = Vector((0, 0, 0))
                    p0, t = p, 0
                poner_matriz(ob, Matrix.Translation(p) @ m.to_quaternion().to_matrix().to_4x4(), f)
        registro["suelta"] = c
    elif tipo == "sentarse":
        c = min(range(d0, d1 + 1), key=lambda f: tray["cadera"][f].z)
        hc = tray["cadera"][c]
        resp = lado_respaldo(ob)
        giro = math.atan2(-adelante.y, -adelante.x) - math.atan2(resp.y, resp.x)  # respaldo detrás
        ob.matrix_world = Matrix.Translation(Vector((hc.x, hc.y, 0)) - adelante * 0.06) @ Matrix.Rotation(giro, 4, "Z")
        asiento = altura_asiento(ob)
        objetivo = hc.z - 0.11  # la articulación de la cadera queda ~11 cm sobre el asiento
        if asiento > 0.05:
            esc_z = max(0.8, min(1.25, objetivo / asiento))
            ob.scale = (esc_z, esc_z, esc_z)
        registro.update({"contacto": c, "asiento_m": round(asiento, 3), "cadera_m": round(hc.z, 3)})
    info.append(registro)


# ───────────────────────── escenarios ─────────────────────────

LUCES = {"calida": (1.0, 0.82, 0.62), "fluorescente": (0.88, 0.95, 1.0), "neutra": (1.0, 0.95, 0.9)}


def construir_escenario(conf: dict, puntos: list, puertas: list, muebles_rutas: dict, info: dict,
                        vistas: list | None = None, puntos_camara: list | None = None):
    """Sala (o exterior) alrededor de los puntos (recorrido del personaje y de la cámara).

    Con puerta: la puerta separa dos espacios (donde empieza el personaje y lo que hay detrás), así puede
    salir por ella. Paredes «salvajes»: una pared que tapa a la cámara en algún cuadro se vuelve invisible
    para la cámara (sigue dando sombra y rebote de luz), como en un set de filmación."""
    tipo = conf.get("tipo", "estudio")
    if tipo == "estudio":
        return
    base = conf  # ya viene completa (estudio/escenarios.json + lo que pidió la toma)
    exterior = conf.get("luz") == "sol"
    tex = conf.get("texturas", {})
    col = bpy.data.collections.new("Escenario")
    bpy.context.scene.collection.children.link(col)

    ex = puertas[0]["eje"].normalized() if puertas else Vector((1, 0, 0))
    ey = Vector((0, 0, 1)).cross(ex)
    loc = lambda p: Vector((p.dot(ex), p.dot(ey)))  # noqa: E731
    mundo = lambda u, v, z=0.0: ex * u + ey * v + Vector((0, 0, z))  # noqa: E731
    giro = Matrix.Rotation(math.atan2(ex.y, ex.x), 4, "Z")
    pts = [loc(p) for p in puntos]
    alto = float(base.get("alto", 2.7))
    margen = 0.6

    def limites(ps, min_u=4.0, min_v=4.0):
        u0, u1 = min(p.x for p in ps) - margen, max(p.x for p in ps) + margen
        v0, v1 = min(p.y for p in ps) - margen, max(p.y for p in ps) + margen
        if u1 - u0 < min_u:
            c = (u0 + u1) / 2
            u0, u1 = c - min_u / 2, c + min_u / 2
        if v1 - v0 < min_v:
            c = (v0 + v1) / 2
            v0, v1 = c - min_v / 2, c + min_v / 2
        return [u0, u1, v0, v1]

    # Espacios: uno solo, o dos separados por el plano de la puerta.
    salas = []
    vp = None
    if puertas and not exterior:
        vp = loc(puertas[0]["bisagra"]).y
        lado_a = [p for p in pts if p.y >= vp]
        lado_b = [p for p in pts if p.y < vp]
        ancho_puerta = [loc(puertas[0]["bisagra"]), loc(puertas[0]["bisagra"] + puertas[0]["eje"] * puertas[0]["ancho"])]
        for lado, signo in ((lado_a, 1), (lado_b, -1)):
            ps = lado + ancho_puerta
            lim = limites(ps, 4.0 if lado else 3.0, 0.1)
            if signo > 0:
                lim[2], lim[3] = vp, max(lim[3], vp + (2.5 if lado else 2.0))
            else:
                lim[2], lim[3] = min(lim[2], vp - (2.5 if lado else 2.0)), vp
            salas.append(lim)
        u0 = min(s_[0] for s_ in salas)
        u1 = max(s_[1] for s_ in salas)
        for s_ in salas:  # mismo ancho: la pared de la puerta es una sola
            s_[0], s_[1] = u0, u1
    else:
        lim = limites(pts)
        if tipo == "ascensor":
            cu, cv = (lim[0] + lim[1]) / 2, (lim[2] + lim[3]) / 2
            lim = [cu - 1.1, cu + 1.1, cv - 1.1, cv + 1.1]  # pequeño: la cámara queda fuera y se ve por las paredes salvajes
        elif tipo == "pasillo":
            if lim[1] - lim[0] > lim[3] - lim[2]:
                c = (lim[2] + lim[3]) / 2
                lim[2], lim[3] = c - 1.2, c + 1.2
            else:
                c = (lim[0] + lim[1]) / 2
                lim[0], lim[1] = c - 1.2, c + 1.2
        elif base.get("muebles") and puntos_camara:
            # Con muebles: la sala crece 1.5 m detrás del personaje (visto desde la cámara), que es donde la
            # cámara los ve. Ajustada al recorrido (0.6 m) no cabían y quedaban detrás de la cámara.
            cams = [loc(p) for p in puntos_camara]
            d = sum(pts, Vector((0, 0))) / len(pts) - sum(cams, Vector((0, 0))) / len(cams)
            if d.length > 1e-3:
                d.normalize()
                if d.x > 0.3:
                    lim[1] += 1.5
                elif d.x < -0.3:
                    lim[0] -= 1.5
                if d.y > 0.3:
                    lim[3] += 1.5
                elif d.y < -0.3:
                    lim[2] -= 1.5
        salas.append(lim)

    mat_piso = material_pbr("piso_escenario", tex.get("piso", {}), 2.0, (0.5, 0.45, 0.4))
    if exterior:
        u0, u1, v0, v1 = salas[0]
        caja("Suelo", (80, 80, 0.05), mundo((u0 + u1) / 2, (v0 + v1) / 2, -0.03), mat_piso, col)
        info["escenario"] = {"tipo": tipo, "tam_m": [round(u1 - u0, 1), round(v1 - v0, 1)]}
        info["escenario"]["muebles"] = _muebles(base, muebles_rutas, col, salas[0], mundo, giro, pts,
                                                [loc(p) for p in (puntos_camara or [])], True)
        return

    mat_pared = material_pbr("pared_escenario", tex.get("pared", {}), 1.5, (0.82, 0.78, 0.72))
    mat_techo = material_color("techo", (0.85, 0.85, 0.83), 0.8)
    color = LUCES.get(base.get("luz", "calida"), LUCES["neutra"])
    mat_panel = material_color("panel_luz", color, 0.5, 0, 2.5)
    g = 0.12
    paredes = []

    def bloque(nombre, uc, vc, du, dv, z0, z1, mat):
        ob = caja(nombre, (du, dv, z1 - z0), Vector((0, 0, 0)), mat, col)
        ob.matrix_world = Matrix.Translation(mundo(uc, vc, (z0 + z1) / 2)) @ giro
        return ob

    def pared(nombre, uc, vc, du, dv, z0=0.0, z1=alto):
        ob = bloque(nombre, uc, vc, du, dv, z0, z1, mat_pared)
        paredes.append(ob)
        return ob

    luces = 0
    for k, (u0, u1, v0, v1) in enumerate(salas):
        piso = bloque(f"Piso_{k}", (u0 + u1) / 2, (v0 + v1) / 2, u1 - u0 + 2 * g, v1 - v0 + 2 * g, -0.05, 0.0, mat_piso)
        piso.name = f"Piso_{k}"
        bloque(f"Techo_{k}", (u0 + u1) / 2, (v0 + v1) / 2, u1 - u0 + 2 * g, v1 - v0 + 2 * g, alto, alto + 0.06, mat_techo)
        pared(f"Pared_oeste_{k}", u0 - g / 2, (v0 + v1) / 2, g, v1 - v0 + 2 * g)
        pared(f"Pared_este_{k}", u1 + g / 2, (v0 + v1) / 2, g, v1 - v0 + 2 * g)
        if vp is None or abs(v0 - vp) > 1e-6:
            pared(f"Pared_sur_{k}", (u0 + u1) / 2, v0 - g / 2, u1 - u0, g)
        if vp is None or abs(v1 - vp) > 1e-6:
            pared(f"Pared_norte_{k}", (u0 + u1) / 2, v1 + g / 2, u1 - u0, g)
        # Luces de techo: paneles que se ven en cuadro + luces de área suaves.
        paso = 2.2
        nu, nv = max(1, round((u1 - u0) / paso)), max(1, round((v1 - v0) / paso))
        for i in range(nu):
            for j in range(nv):
                uc = u0 + (i + 0.5) * (u1 - u0) / nu
                vc = v0 + (j + 0.5) * (v1 - v0) / nv
                panel = bloque(f"Panel_{k}_{i}_{j}", uc, vc, 1.2, 0.3, alto - 0.02, alto, mat_panel)
                panel.visible_shadow = False
                ld = bpy.data.lights.new(f"Techo_{k}_{i}_{j}", "AREA")
                ld.shape, ld.size, ld.size_y = "RECTANGLE", 1.2, 0.3
                ld.energy, ld.color = 70.0, color
                lz = bpy.data.objects.new(ld.name, ld)
                col.objects.link(lz)
                lz.matrix_world = Matrix.Translation(mundo(uc, vc, alto - 0.04)) @ giro
                luces += 1
    if vp is not None:  # pared de la puerta, con el hueco
        u0, u1 = salas[0][0], salas[0][1]
        pz = puertas[0]
        ub, um = loc(pz["bisagra"]).x, loc(pz["bisagra"] + pz["eje"] * pz["ancho"]).x
        h0, h1 = min(ub, um) - 0.04, max(ub, um) + 0.04
        if h0 > u0:
            pared("Tabique_a", (u0 + h0) / 2, vp, h0 - u0, g)
        if h1 < u1:
            pared("Tabique_b", (h1 + u1) / 2, vp, u1 - h1, g)
        pared("Dintel", (h0 + h1) / 2, vp, h1 - h0, g, pz["alto"] + 0.02, alto)

    # Paredes salvajes: las que se cruzan entre la cámara y el personaje dejan de verse en cámara.
    salvajes = []
    if vistas:
        bpy.context.view_layer.update()
        for ob in paredes:
            inv = ob.matrix_world.inverted()
            for cam_p, obj_p in vistas:
                o, d = inv @ cam_p, (inv @ obj_p) - (inv @ cam_p)
                dist = d.length
                hit, *_ = ob.ray_cast(o, d.normalized(), distance=dist) if dist > 1e-4 else (False,)
                if hit:  # como retirar la pared del set: no se ve ni hace sombra (sí rebota luz)
                    ob.visible_camera = False
                    ob.visible_shadow = False
                    salvajes.append(ob.name)
                    break
    mundo_esc = bpy.context.scene.world  # adentro, el cielo solo aporta un poco de luz de relleno
    if mundo_esc and mundo_esc.node_tree and "Background" in mundo_esc.node_tree.nodes:
        mundo_esc.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.2
    info["escenario"] = {"tipo": tipo, "espacios": [[round(x, 1) for x in s_] for s_ in salas], "alto_m": alto,
                         "luces": luces, "puertas": len(puertas), "paredes_salvajes": salvajes}
    info["escenario"]["muebles"] = _muebles(base, muebles_rutas, col, salas[0], mundo, giro, pts,
                                            [loc(p) for p in (puntos_camara or [])])


def _muebles(base, rutas, col, lim, mundo, giro, pts, pts_cam=(), exterior=False):
    """Muebles contra las paredes, mirando al centro y lejos del recorrido y de la cámara."""
    u0, u1, v0, v1 = lim
    lista = base.get("muebles", [])
    if not lista:
        return []
    puestos = []
    huecos = []  # (u, v, giro, hacia la pared en u, en v)
    paso = 1.3
    for k in range(int((u1 - u0) / paso)):
        u = u0 + 0.7 + k * paso
        huecos += [(u, v1 - 0.45, math.pi, 0, 1), (u, v0 + 0.45, 0.0, 0, -1)]
    for k in range(int((v1 - v0) / paso)):
        v = v0 + 0.7 + k * paso
        huecos += [(u0 + 0.45, v, -math.pi / 2, -1, 0), (u1 - 0.45, v, math.pi / 2, 1, 0)]
    lejos = lambda h, ps, d: not ps or min((Vector((h[0], h[1])) - p).length for p in ps) > d  # noqa: E731
    libres = [h for h in huecos if lejos(h, pts, 1.6 if exterior else 1.0) and lejos(h, list(pts_cam), 1.4)]
    # Primero los huecos que la cámara ve (detrás del personaje, mirando desde la cámara); después, los más
    # lejanos del recorrido. Medido en GPU: ordenar solo por lejanía dejaba el sillón detrás de la cámara.
    c_pts = sum((Vector(p) for p in pts), Vector((0, 0))) / len(pts) if pts else Vector((0, 0))
    cams = list(pts_cam)
    c_cam = sum((Vector(p) for p in cams), Vector((0, 0))) / len(cams) if cams else None

    def angulo_cam(h):
        """Ángulo entre la línea cámara→personaje y cámara→hueco (0 = justo detrás del personaje)."""
        if c_cam is None:
            return 0.0
        a_, b_ = c_pts - c_cam, Vector((h[0], h[1])) - c_cam
        if a_.length < 1e-6 or b_.length < 1e-6:
            return 180.0
        return math.degrees(a_.angle(b_))

    def detras(h):
        return c_cam is None or (Vector((h[0], h[1])) - c_cam).length > (c_pts - c_cam).length

    # El cuadro vertical es angosto: primero lo que queda dentro de ~25° a los lados del personaje y detrás de
    # él (se ve en el plano), en orden de cercanía a ese eje; después el resto, lejos del recorrido.
    libres.sort(key=lambda h: (not (detras(h) and angulo_cam(h) < 25), angulo_cam(h) if detras(h) else 180,
                               -min((Vector((h[0], h[1])) - p).length for p in pts) if pts else 0))
    for nombre, (u, v, r, du, dv) in zip(lista, libres):
        if nombre not in rutas:
            continue
        ob = crear_objeto({"ruta": rutas[nombre], "tipo": nombre})
        ob.matrix_world = Matrix.Translation(mundo(u, v)) @ giro @ Matrix.Rotation(r, 4, "Z")
        # Respaldo contra la pared: se mide dónde está la parte alta del mueble y se gira hasta que
        # apunte a la pared (el giro fijo dejaba sillones y sofás mirando a la pared).
        bpy.context.view_layer.update()
        respaldo = respaldo_claro(ob)
        if respaldo is not None:
            pared = mundo(u + du, v + dv) - mundo(u, v)
            pared.z = 0
            if pared.length > 1e-6:
                ang = math.atan2(respaldo.x * pared.y - respaldo.y * pared.x, respaldo.dot(pared.normalized()))
                pos = ob.matrix_world.to_translation()
                ob.matrix_world = Matrix.Translation(pos) @ Matrix.Rotation(ang, 4, "Z") @ \
                    Matrix.Translation(-pos) @ ob.matrix_world
        puestos.append({"mueble": nombre, "u": round(u, 2), "v": round(v, 2),
                        "en_cuadro": bool(detras((u, v)) and angulo_cam((u, v)) < 25),
                        "respaldo_a_la_pared": respaldo is not None})
        for o in [ob] + list(ob.children_recursive):
            for c in o.users_collection:
                c.objects.unlink(o)
            col.objects.link(o)
    return puestos
