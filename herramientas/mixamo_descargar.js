// EDDIE STUDIO 3D — Descarga por lotes de animaciones de Mixamo (FBX, sin piel, 30 fps).
//
// CÓMO USARLO
//  1. Entra a https://www.mixamo.com e inicia sesión.
//  2. En la pestaña "Characters" selecciona tu personaje (ej. Remy). Las animaciones se adaptan a él.
//  3. Abre la consola del navegador: F12 → pestaña "Console".
//  4. Pega TODO este script y pulsa Enter.
//  5. Si el navegador pregunta "¿Permitir descargas múltiples?", pulsa "Permitir".
//  6. Al final verás un resumen. Sube los .fbx a: Diseños 3d/biblioteca/_entrada/mixamo/animaciones/
//
// No es una herramienta oficial de Adobe: usa las mismas llamadas internas que la página de Mixamo.
// Tu contraseña no se usa: el script aprovecha la sesión que ya tienes abierta en esta pestaña.
// Uso permitido por Adobe: animaciones libres de regalías en tus proyectos; no se redistribuyen los archivos.

(async () => {
  // ─────────────── LISTA (puedes editarla) ───────────────
  // [término de búsqueda en inglés, ¿en el lugar? (caminar/correr), nombre corto del archivo]
  const LISTA = [
    ["idle", false, "parado_reposo"],
    ["walking", true, "caminar"],
    ["running", true, "correr"],
    ["sitting idle", false, "sentado_reposo"],
    ["stand to sit", false, "sentarse"],
    ["sit to stand", false, "levantarse_silla"],
    ["standing up", false, "levantarse_piso"],
    ["turn", false, "girar"],
    ["injured walk", true, "caminar_herido"],
    ["injured idle", false, "herido_reposo"],
    ["limping", true, "cojear"],
    ["stumble", false, "tropezar"],
    ["falling", false, "caer"],
    ["fall flat", false, "caer_de_frente"],
    ["getting up", false, "levantarse_caido"],
    ["knee", false, "dolor_rodilla"],
    ["holding", false, "sujetarse"],
    ["talking", false, "hablar"],
    ["surprised", false, "sorpresa"],
    ["scared", false, "miedo"],
    ["crying", false, "llorar"],
    ["sad idle", false, "triste"],
    ["nervous", false, "nervioso"],
    ["thinking", false, "pensar"],
    ["shrugging", false, "encogerse_hombros"],
    ["pointing", false, "senalar"],
    ["drinking", false, "beber"],
    ["eating", false, "comer"],
    ["texting", false, "mensajear_celular"],
    ["sleeping", false, "dormir"],
    ["yawn", false, "bostezar"],
    ["stretching", false, "estirarse"],
    ["opening door", false, "abrir_puerta"],
    ["picking up", false, "recoger_objeto"],
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
  const limpiar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "");

  // Personaje seleccionado en la página.
  let personaje;
  try {
    const p = await api("https://www.mixamo.com/api/v1/characters/primary");
    personaje = { id: p.primary_character_id, nombre: p.primary_character_name };
  } catch (e) { console.error("❌ No pude leer el personaje seleccionado:", e.message); return; }
  if (!personaje.id) { console.error("❌ Selecciona primero un personaje en la pestaña Characters."); return; }
  console.log(`🎬 Personaje: ${personaje.nombre} (${personaje.id}). Descargando ${LISTA.length} animaciones…`);

  async function bajarArchivo(url, nombre) {
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = nombre;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    } catch (e) {
      // Si el servidor no permite leerlo desde la página, se abre el enlace (el navegador lo descarga igual).
      console.warn(`   (descarga directa de ${nombre}; el archivo puede quedar con el nombre de Mixamo)`);
      const a = document.createElement("a");
      a.href = url; a.download = nombre; a.target = "_blank";
      document.body.appendChild(a); a.click(); a.remove();
    }
  }

  const resumen = [];
  for (let i = 0; i < LISTA.length; i++) {
    const [busqueda, enLugar, corto] = LISTA[i];
    const num = String(i + 1).padStart(2, "0");
    try {
      const res = await api(`https://www.mixamo.com/api/v1/products?page=1&limit=24&order=&type=Motion&query=${encodeURIComponent(busqueda)}`);
      const lista = (res.results || []).filter((x) => x.type === "Motion");
      if (!lista.length) throw new Error("sin resultados");
      const exacta = lista.find((x) => (x.name || "").toLowerCase() === busqueda.toLowerCase());
      const elegido = exacta || lista[0];

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

      const archivo = `${num}_${corto}__${limpiar(elegido.name)}.fbx`;
      await bajarArchivo(url, archivo);
      console.log(`✅ ${num}/${LISTA.length} ${archivo}`);
      resumen.push({ "#": num, busqueda, animacion: elegido.name, archivo, estado: "OK" });
    } catch (e) {
      console.error(`❌ ${num}/${LISTA.length} "${busqueda}": ${e.message}`);
      resumen.push({ "#": num, busqueda, animacion: "-", archivo: "-", estado: "ERROR: " + e.message });
    }
    await dormir(PAUSA_MS);
  }
  console.table(resumen);
  const fallos = resumen.filter((r) => r.estado !== "OK").length;
  console.log(fallos ? `⚠️ Terminado con ${fallos} error(es). Copia la tabla y pásasela a Claude.`
                     : "🎉 Terminado sin errores. Sube los .fbx a Diseños 3d/biblioteca/_entrada/mixamo/animaciones/");
})();
