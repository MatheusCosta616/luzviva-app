// LuzViva: front do MVP. Monta o DOM com textContent (sem innerHTML) para nao injetar HTML.
const ROTULO = { apagada: "Apagada", insuficiente: "Insuficiente", ok: "Acesa" };
const COR = { apagada: "#ff5c5c", insuficiente: "#f5b83d", ok: "#3ccf8e" };

function el(tag, props = {}, ...filhos) {
  const n = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  });
  filhos.forEach((f) => n.append(f instanceof Node ? f : document.createTextNode(String(f))));
  return n;
}
const tag = (s) => el("span", { class: `tag ${s}` }, ROTULO[s] || s);

async function api(caminho, opcoes) {
  const r = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail ? JSON.stringify(corpo.detail) : `Erro ${r.status}`);
  return corpo;
}

// ----- abas (teclado: setas esquerda/direita) -----
const abas = [...document.querySelectorAll('[role="tab"]')];
let mapa;
function ativar(aba) {
  abas.forEach((a) => {
    const sel = a === aba;
    a.setAttribute("aria-selected", sel);
    a.tabIndex = sel ? 0 : -1;
    document.getElementById(a.getAttribute("aria-controls")).hidden = !sel;
  });
  aba.focus();
  if (aba.id === "t-mapa" && mapa) setTimeout(() => mapa.invalidateSize(), 50);
  if (aba.id === "t-chamados") carregarChamados();
}
abas.forEach((a, i) => {
  a.tabIndex = i === 0 ? 0 : -1;
  a.addEventListener("click", () => ativar(a));
  a.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") ativar(abas[(i + 1) % abas.length]);
    if (e.key === "ArrowLeft") ativar(abas[(i - 1 + abas.length) % abas.length]);
  });
});

// ----- mapa -----
async function carregarMapa() {
  const { dados } = await api("/api/luminarias");
  mapa = L.map("mapa").setView([-23.59, -46.70], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap",
  }).addTo(mapa);
  dados.forEach((l) => {
    const popup = el("div", {},
      el("strong", {}, l.placa), el("br"), l.endereco, el("br"),
      `${ROTULO[l.situacao]} · ${l.ultimo_lux} lux`);
    L.circleMarker([l.lat, l.lon], {
      radius: 8, color: "#111", weight: 1, fillColor: COR[l.situacao], fillOpacity: 0.95,
    }).bindPopup(popup).bindTooltip(`${l.placa}: ${ROTULO[l.situacao]}`).addTo(mapa);
  });
}

// ----- fila -----
async function carregarFila() {
  const { dados } = await api("/api/fila");
  const corpo = document.querySelector("#tabela-fila tbody");
  corpo.replaceChildren(...dados.map((f, i) => {
    const botao = el("button", { type: "button" }, "Abrir chamado");
    botao.addEventListener("click", async () => {
      botao.disabled = true;
      try {
        await api("/api/chamados", { method: "POST", body: JSON.stringify({
          placa: f.placa, area_piloto: areaDe(f.subprefeitura), prioridade: f.prioridade,
          situacao_detectada: f.situacao, origem: "site" }) });
        botao.textContent = "Chamado aberto";
      } catch (e) { botao.textContent = "Já aberto"; }
    });
    return el("tr", {}, el("td", {}, i + 1), el("td", {}, f.placa), el("td", {}, f.endereco),
      el("td", {}, tag(f.situacao)), el("td", {}, f.ultimo_lux), el("td", {}, f.ocorrencias_app),
      el("td", {}, el("strong", {}, f.prioridade)), el("td", {}, botao));
  }));
}
const areaDe = (sub) => ({ "Se": "SE", "Pinheiros": "PINHEIROS", "Campo Limpo": "CAMPO LIMPO" })[sub];

// ----- painel -----
async function carregarPainel() {
  const { dados } = await api("/api/painel");
  document.getElementById("cards").replaceChildren(...dados.map((p) => el("article", { class: "card" },
    el("h3", {}, p.subprefeitura),
    el("div", { class: "num" }, `${p.pct_com_falha}%`), el("div", {}, "das luminárias com falha"),
    el("dl", {},
      el("dt", {}, "Monitoradas"), el("dd", {}, p.luminarias_monitoradas),
      el("dt", {}, "Apagadas"), el("dd", {}, p.apagadas),
      el("dt", {}, "Insuficientes"), el("dd", {}, p.insuficientes),
      el("dt", {}, "Horas-luminária no escuro/noite"), el("dd", {}, p.horas_luminaria_no_escuro_noite)))));
}

// ----- chamados -----
async function carregarChamados() {
  const { dados } = await api("/api/chamados");
  document.getElementById("sem-chamados").hidden = dados.length > 0;
  const corpo = document.querySelector("#tabela-chamados tbody");
  corpo.replaceChildren(...dados.map((c) => {
    const sel = el("select", { "aria-label": `Status do chamado ${c.id_chamado}` },
      ...["aberto", "em_atendimento", "concluido", "cancelado"].map((s) => {
        const o = el("option", { value: s }, s.replace("_", " "));
        if (s === c.status) o.selected = true;
        return o;
      }));
    sel.addEventListener("change", async () => {
      await api(`/api/chamados/${encodeURIComponent(c.id_chamado)}`, { method: "PATCH", body: JSON.stringify({ status: sel.value }) });
      carregarChamados();
    });
    return el("tr", {}, el("td", {}, c.id_chamado), el("td", {}, c.placa), el("td", {}, c.prioridade),
      el("td", {}, c.status.replace("_", " ")), el("td", {}, c.aberto_em.replace("T", " ")), el("td", {}, sel));
  }));
}

// ----- reportar -----
document.getElementById("form-ocorrencia").addEventListener("submit", async (e) => {
  e.preventDefault();
  const dados = Object.fromEntries(new FormData(e.target));
  dados.placa = dados.placa.trim().toUpperCase();
  const saida = document.getElementById("retorno-ocorrencia");
  try {
    const r = await api("/api/ocorrencias", { method: "POST", body: JSON.stringify(dados) });
    saida.textContent = `Obrigado! Relato ${r.id_ocorrencia} registrado.`;
    e.target.reset();
  } catch (err) { saida.textContent = `Não foi possível enviar: confira a placa (IP + 7 dígitos).`; }
});

// ----- assistente -----
document.getElementById("form-assistente").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pergunta = new FormData(e.target).get("pergunta");
  const caixa = document.getElementById("resposta");
  caixa.replaceChildren("Consultando...");
  try {
    const r = await api("/api/assistente", { method: "POST", body: JSON.stringify({ pergunta }) });
    caixa.replaceChildren(el("p", {}, r.resposta),
      ...r.fontes.map((f) => el("p", { class: "fonte" }, `Fonte: ${f.titulo} (${f.trecho})`)));
  } catch (err) { caixa.replaceChildren("Assistente indisponível no momento."); }
});

carregarMapa().catch(() => {});
carregarFila(); carregarPainel();
