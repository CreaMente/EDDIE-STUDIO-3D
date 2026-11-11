// EDDIE STUDIO 3D — Descarga por lotes de animaciones de Mixamo (FBX, sin piel, 30 fps).
//
// CÓMO USARLO
//  1. Entra a https://www.mixamo.com e inicia sesión.
//  2. En la pestaña "Characters" selecciona tu personaje (ej. Remy). Las animaciones se adaptan a él.
//  3. Abre la consola del navegador: F12 → pestaña "Console".
//  4. Pega TODO este script y pulsa Enter.
//  5. ANTES de pegarlo, permite las descargas automáticas para mixamo.com (si no, Chrome solo baja la
//     primera): chrome://settings/content/automaticDownloads → "Pueden descargar varios archivos
//     automáticamente" → Agregar → [*.]mixamo.com
//  6. Al final verás un resumen. Sube los .fbx a: Diseños 3d/biblioteca/_entrada/mixamo/animaciones/
//
// No es una herramienta oficial de Adobe: usa las mismas llamadas internas que la página de Mixamo.
// Tu contraseña no se usa: el script aprovecha la sesión que ya tienes abierta en esta pestaña.
// Uso permitido por Adobe: animaciones libres de regalías en tus proyectos; no se redistribuyen los archivos.

(async () => {
  // ─────────────── LISTA (puedes editarla) ───────────────
  // [búsqueda en inglés, ¿en el lugar? (ciclos de caminar/correr), nombre corto, categoría, interacción]
  // interacción = qué objeto usa la animación y con qué mano ("puerta:R", "agarrar:R", "sentarse",
  // "telefono:R", "taza:R"…): el estudio coloca el objeto solo y lo hace seguir la mano.
  // Las 30 primeras son las de la primera tanda: si ya las tienes, puedes borrarlas de la lista.
  const LISTA = [
    // — básicas (primera tanda) —
    ["idle", false, "parado_reposo", "reposo"],
    ["walking", true, "caminar", "locomocion"],
    ["running", true, "correr", "locomocion"],
    ["sitting idle", false, "sentado_reposo", "sentado", "sentado"],
    ["stand to sit", false, "sentarse", "sentado", "sentarse"],
    ["sit to stand", false, "levantarse_silla", "sentado", "sentado"],
    ["standing up", false, "levantarse_piso", "caidas"],
    ["turn", false, "girar", "locomocion"],
    ["injured walk", true, "caminar_herido", "dolor"],
    ["injured idle", false, "herido_reposo", "dolor"],
    ["stumble", false, "tropezar", "caidas"],
    ["falling", false, "caer", "caidas"],
    ["fall flat", false, "caer_de_frente", "caidas"],
    ["getting up", false, "levantarse_caido", "caidas"],
    ["talking", false, "hablar", "conversacion"],
    ["surprised", false, "sorpresa", "emociones"],
    ["scared", false, "miedo", "emociones"],
    ["crying", false, "llorar", "emociones"],
    ["sad idle", false, "triste", "emociones"],
    ["nervous", false, "nervioso", "emociones"],
    ["thinking", false, "pensar", "conversacion"],
    ["shrugging", false, "encogerse_hombros", "conversacion"],
    ["pointing", false, "senalar", "conversacion"],
    ["drinking", false, "beber", "objetos", "taza:R"],
    ["texting", false, "mensajear_celular", "objetos", "telefono:R"],
    ["sleeping", false, "dormir", "acostado"],
    ["yawn", false, "bostezar", "reposo"],
    ["stretching", false, "estirarse", "reposo"],
    ["opening door", false, "abrir_puerta", "objetos", "puerta:R"],
    ["picking up", false, "recoger_objeto", "objetos", "agarrar:R"],
    // — locomoción —
    ["jogging", true, "trotar", "locomocion"],
    ["walking backwards", true, "caminar_atras", "locomocion"],
    ["sneak walk", true, "caminar_sigilo", "locomocion"],
    ["drunk walk", true, "caminar_mareado", "locomocion"],
    ["sad walk", true, "caminar_triste", "locomocion"],
    ["happy walk", true, "caminar_feliz", "locomocion"],
    ["start walking", false, "empezar_caminar", "locomocion"],
    ["stop walking", false, "detenerse", "locomocion"],
    ["left turn", false, "girar_izquierda", "locomocion"],
    ["right turn", false, "girar_derecha", "locomocion"],
    ["running to stop", false, "frenar_corriendo", "locomocion"],
    ["ascending stairs", true, "subir_escaleras", "locomocion"],
    ["descending stairs", true, "bajar_escaleras", "locomocion"],
    ["jump", false, "saltar", "locomocion"],
    ["running jump", false, "saltar_corriendo", "locomocion"],
    ["crouch walk", true, "caminar_agachado", "locomocion"],
    ["crawling", true, "gatear", "locomocion"],
    ["looking around", false, "mirar_alrededor", "reposo"],
    // — reposo y conversación —
    ["breathing idle", false, "respirar_reposo", "reposo"],
    ["happy idle", false, "feliz_reposo", "reposo"],
    ["bored", false, "aburrido", "reposo"],
    ["waving", false, "saludar_mano", "conversacion"],
    ["clapping", false, "aplaudir", "conversacion"],
    ["cheering", false, "celebrar", "emociones"],
    ["laughing", false, "reir", "emociones"],
    ["agreeing", false, "asentir", "conversacion"],
    ["head nod yes", false, "si_cabeza", "conversacion"],
    ["shaking head no", false, "no_cabeza", "conversacion"],
    ["arguing", false, "discutir", "conversacion"],
    ["angry", false, "enojado", "emociones"],
    ["whispering", false, "susurrar", "conversacion"],
    ["explaining", false, "explicar", "conversacion"],
    ["standing greeting", false, "saludar", "conversacion"],
    ["talking on phone", false, "hablar_telefono", "objetos", "telefono:R"],
    // — emociones y dolor —
    ["terrified", false, "aterrado", "emociones"],
    ["defeated", false, "derrotado", "emociones"],
    ["disappointed", false, "decepcionado", "emociones"],
    ["relieved sigh", false, "alivio", "emociones"],
    ["excited", false, "emocionado", "emociones"],
    ["victory", false, "victoria", "emociones"],
    ["sick", false, "enfermo", "dolor"],
    ["dizzy", false, "mareado", "dolor"],
    ["headache", false, "dolor_cabeza", "dolor"],
    ["stomach pain", false, "dolor_estomago", "dolor"],
    ["kneeling", false, "arrodillarse", "dolor"],
    ["holding knee", false, "sujetar_rodilla", "dolor"],
    ["coughing", false, "toser", "dolor"],
    ["shivering", false, "temblar_frio", "dolor"],
    // — caídas y golpes —
    ["slip", false, "resbalar", "caidas"],
    ["fainting", false, "desmayarse", "caidas"],
    ["dying", false, "desplomarse", "caidas"],
    ["hit reaction", false, "recibir_golpe", "caidas"],
    ["knocked down", false, "derribado", "caidas"],
    ["laying idle", false, "acostado_reposo", "acostado"],
    // — sentado y acostado —
    ["sitting talking", false, "sentado_hablar", "sentado", "sentado"],
    ["sitting laughing", false, "sentado_reir", "sentado", "sentado"],
    ["sitting sad", false, "sentado_triste", "sentado", "sentado"],
    ["sitting thinking", false, "sentado_pensar", "sentado", "sentado"],
    ["sitting clap", false, "sentado_aplaudir", "sentado", "sentado"],
    ["sitting drinking", false, "sentado_beber", "sentado", "taza:R"],
    ["sitting typing", false, "sentado_escribir_pc", "sentado", "sentado"],
    ["sitting reading", false, "sentado_leer", "sentado", "libro:R"],
    ["sitting texting", false, "sentado_celular", "sentado", "telefono:R"],
    ["sitting to laying", false, "sentado_a_acostado", "acostado"],
    ["getting out of bed", false, "levantarse_cama", "acostado"],
    // — objetos —
    ["closing door", false, "cerrar_puerta", "objetos", "puerta:R"],
    ["knocking on door", false, "tocar_puerta", "objetos", "tocar:R"],
    ["putting down", false, "dejar_objeto", "objetos", "soltar:R"],
    ["lifting box", false, "levantar_caja", "objetos", "caja"],
    ["carrying box", true, "cargar_caja", "objetos", "caja"],
    ["throwing", false, "lanzar", "objetos", "lanzar:R"],
    ["pushing", false, "empujar", "objetos"],
    ["pulling", false, "jalar", "objetos"],
    ["button pushing", false, "presionar_boton", "objetos", "boton:R"],
    ["looking at watch", false, "mirar_reloj", "objetos"],
    ["typing", false, "escribir_teclado", "objetos"],
    ["reading", false, "leer", "objetos", "libro:R"],
    ["taking photo", false, "tomar_foto", "objetos", "telefono:R"],
    ["searching pockets", false, "buscar_bolsillos", "objetos"],
    // — acción —
    ["fight idle", false, "pelea_reposo", "accion"],
    ["punching", false, "golpear", "accion"],
    ["kicking", false, "patear", "accion"],
    ["dodging", false, "esquivar", "accion"],
    ["running scared", true, "huir", "accion"],
    ["hiding", false, "esconderse", "accion"],
    ["climbing", false, "trepar", "accion"],
    ["push up", false, "flexiones", "ejercicio"],
    ["jumping jacks", false, "saltos_tijera", "ejercicio"],
  ];
  const PAUSA_MS = 1500;          // pausa entre animaciones (no saturar el servidor)
  const ESPERA_MAX_S = 120;       // tiempo máximo esperando a que Mixamo prepare cada archivo

  // ─────────────── no hace falta editar debajo ───────────────
  const token = localStorage.access_token;
  if (!token) { console.error("❌ No encuentro tu sesión. Inicia sesión en mixamo.com y vuelve a pegar el script."); return; }
  const H = { "Accept": "application/json", "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`, "X-Api-Key": "mixamo2", "X-Requested-With": "XMLHttpRequest" };
  const api = async (url, opts = {}) => {
    const r = await fetch(url, { headers: H, ...opts });
    if (!r.ok && r.status !== 202) throw new Error(`HTTP ${r.status} en ${url}`);
    return r.json();
  };
  const dormir = (ms) => new Promise((ok) => setTimeout(ok, ms));

  // Personaje seleccionado en la página.
  let personaje;
  try {
    const p = await api("https://www.mixamo.com/api/v1/characters/primary");
    personaje = { id: p.primary_character_id, nombre: p.primary_character_name };
  } catch (e) { console.error("❌ No pude leer el personaje seleccionado:", e.message); return; }
  if (!personaje.id) { console.error("❌ Selecciona primero un personaje en la pestaña Characters."); return; }
  console.log(`🎬 Personaje: ${personaje.nombre} (${personaje.id}). Descargando ${LISTA.length} animaciones…`);

  // La página de Mixamo no permite leer el archivo desde el script (política de seguridad), así que se usa
  // la descarga normal del navegador: el archivo conserva el nombre que le pone Mixamo (p. ej. "Walking.fbx").
  // La relación nombre de Mixamo → nombre en español queda en el índice que se descarga al final.
  function bajarArchivo(url) {
    const a = document.createElement("a");
    a.href = url; a.rel = "noopener";
    document.body.appendChild(a); a.click(); a.remove();
  }

  const resumen = [];
  for (let i = 0; i < LISTA.length; i++) {
    const [busqueda, enLugar, corto, categoria, interaccion] = LISTA[i];
    const num = String(i + 1).padStart(2, "0");
    try {
      const res = await api(`https://www.mixamo.com/api/v1/products?page=1&limit=24&order=&type=Motion&query=${encodeURIComponent(busqueda)}`);
      const lista = (res.results || []).filter((x) => x.type === "Motion");
      if (!lista.length) throw new Error("sin resultados");
      // Se elige el resultado que más palabras de la búsqueda contiene (el primero de Mixamo a veces es
      // otra cosa: «limping» devolvía «Running Tired»). Si ninguno coincide bien, se salta y se avisa.
      const palabras = busqueda.toLowerCase().split(/\s+/);
      const puntos = (x) => {
        const n = (x.name || "").toLowerCase();
        if (n === busqueda.toLowerCase()) return 100;
        return palabras.filter((w) => n.includes(w.replace(/ing$/, ""))).length;
      };
      const ordenada = [...lista].sort((x, y) => puntos(y) - puntos(x));
      const elegido = ordenada[0];
      if (puntos(elegido) < Math.ceil(palabras.length / 2)) {
        throw new Error("sin coincidencia clara; Mixamo ofrece: " + lista.slice(0, 4).map((x) => x.name).join(" | "));
      }

      const prod = await api(`https://www.mixamo.com/api/v1/products/${elegido.id}?similar=0&character_id=${personaje.id}`);
      const gms = prod.details.gms_hash;
      const hash = { ...gms, params: (gms.params || []).map((p) => p[1]).join(",") };
      if ("inplace" in hash) hash.inplace = enLugar;

      await api("https://www.mixamo.com/api/v1/animations/export", {
        method: "POST",
        body: JSON.stringify({
          character_id: personaje.id, gms_hash: [hash], product_name: elegido.name, type: "Motion",
          preferences: { format: "fbx7", skin: "false", fps: "30", reducekf: "0" },
        }),
      });

      let url = null;
      for (let t = 0; t < ESPERA_MAX_S; t += 2) {
        const m = await api(`https://www.mixamo.com/api/v1/characters/${personaje.id}/monitor`);
        if (m.status === "completed") { url = m.job_result; break; }
        if (m.status === "failed") throw new Error("Mixamo no pudo preparar el archivo: " + (m.message || ""));
        await dormir(2000);
      }
      if (!url) throw new Error("tiempo de espera agotado");

      const archivo = `${elegido.name}.fbx`;
      bajarArchivo(url);
      console.log(`✅ ${num}/${LISTA.length} ${archivo}  →  ${corto}`);
      resumen.push({ "#": num, busqueda, animacion: elegido.name, archivo, nombre: corto, en_lugar: enLugar,
                     categoria: categoria || "", interaccion: interaccion || "", estado: "OK" });
    } catch (e) {
      console.error(`❌ ${num}/${LISTA.length} "${busqueda}": ${e.message}`);
      resumen.push({ "#": num, busqueda, animacion: "-", archivo: "-", estado: "ERROR: " + e.message });
    }
    await dormir(PAUSA_MS);
  }
  console.table(resumen);
  // Índice para el estudio: qué archivo de Mixamo corresponde a cada acción (se sube junto con los .fbx).
  const indice = new Blob([JSON.stringify({ personaje, animaciones: resumen }, null, 1)], { type: "application/json" });
  const ai = document.createElement("a");
  ai.href = URL.createObjectURL(indice); ai.download = "mixamo_indice.json";
  document.body.appendChild(ai); ai.click(); ai.remove();
  const fallos = resumen.filter((r) => r.estado !== "OK").length;
  console.log(fallos ? `⚠️ Terminado con ${fallos} error(es). Copia la tabla y pásasela a Claude.`
                     : "🎉 Terminado sin errores. Sube los .fbx y mixamo_indice.json a Diseños 3d/biblioteca/_entrada/mixamo/animaciones/");
})();
