import { useEffect } from 'react'

/**
 * Integração do VLibras (plugin oficial do gov.br) num app React.
 *
 * O plugin espera uma estrutura DOM fixa no <body> e um script externo; depois
 * um `new VLibras.Widget(...)` injeta o avatar. Como aqui ele é LIGÁVEL, este
 * componente cria a estrutura + inicializa quando `ativo` fica true e remove
 * tudo quando fica false — sem recarregar a página.
 *
 * Requisitos: o navegador precisa alcançar vlibras.gov.br (internet). Se não
 * alcançar, falha em silêncio — o resto do painel segue normal.
 */

const SRC = 'https://vlibras.gov.br/app/vlibras-plugin.js'
const APP = 'https://vlibras.gov.br/app'
const ID_RAIZ = 'vlibras-raiz'

let promessaScript = null
function carregarScript() {
  if (window.VLibras) return Promise.resolve()
  if (promessaScript) return promessaScript
  promessaScript = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SRC
    s.async = true
    s.onload = resolve
    s.onerror = () => { promessaScript = null; reject(new Error('VLibras indisponível')) }
    document.body.appendChild(s)
  })
  return promessaScript
}

function criarDom() {
  if (document.getElementById(ID_RAIZ)) return
  const raiz = document.createElement('div')
  raiz.id = ID_RAIZ
  raiz.setAttribute('vw', '')
  raiz.className = 'enabled'
  raiz.innerHTML =
    '<div vw-access-button class="active"></div>' +
    '<div vw-plugin-wrapper><div class="vw-plugin-top-wrapper"></div></div>'
  document.body.appendChild(raiz)
}

function removerDom() {
  document.getElementById(ID_RAIZ)?.remove()
}

export default function VLibrasWidget({ ativo }) {
  useEffect(() => {
    if (!ativo) {
      removerDom()
      return undefined
    }
    let cancelado = false
    criarDom()
    carregarScript()
      .then(() => {
        if (cancelado || !window.VLibras) return
        try { new window.VLibras.Widget(APP) } catch { /* já inicializado / ignora */ }
      })
      .catch(() => { /* sem acesso ao gov.br: silencioso, não quebra o painel */ })
    return () => { cancelado = true }
  }, [ativo])

  return null
}
