/**
 * Camada de API. Os endpoints, métodos e formatos de payload são EXATAMENTE
 * os mesmos usados por dashboard.js e common.js — nenhum contrato foi alterado.
 *
 * Todas as respostas do backend seguem { success: bool, ...dados } ou
 * { success: false, error: string }, e esse formato foi preservado.
 */

async function requisicao(url, options) {
  const response = await fetch(url, options)
  return response.json()
}

const jsonHeaders = { 'Content-Type': 'application/json' }

/* ── Operadores ─────────────────────────────────────────────────── */

export function listarOperadores() {
  return requisicao('/api/operadores')
}

export function obterOperador(id) {
  return requisicao(`/api/operadores/${id}`)
}

export function criarOperador(payload) {
  return requisicao('/api/operadores', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function atualizarOperador(id, payload) {
  return requisicao(`/api/operadores/${id}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })
}

export function excluirOperador(id) {
  return requisicao(`/api/operadores/${id}`, { method: 'DELETE' })
}

export function listarEventosOperador(id) {
  return requisicao(`/api/operadores/${id}/eventos`)
}

export function enviarComando(id, comando, target = 'ambos') {
  return requisicao(`/api/operadores/${id}/comando`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ comando, target }),
  })
}

/* ── Servidor ───────────────────────────────────────────────────── */

export function obterSaudeServidor() {
  return requisicao('/api/servidor/saude')
}

export function obterConfigServidor() {
  return requisicao('/api/servidor/config')
}

export function salvarConfigServidor(host, port) {
  return requisicao('/api/servidor/config', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ host, port }),
  })
}
