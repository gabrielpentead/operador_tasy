/**
 * Chamadas de gerenciamento da programação de reinícios automáticos dos
 * painéis. Usam o cookie de sessão (credentials:'include') — as rotas são admin.
 */
const base = '/api/reinicios'

async function req(caminho, opcoes = {}) {
  const r = await fetch(base + caminho, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opcoes,
  })
  let dados = {}
  try { dados = await r.json() } catch { /* sem corpo */ }
  return { ok: r.ok, status: r.status, ...dados }
}

export const reiniciosApi = {
  listar:  ()      => req(''),
  criar:   (dados) => req('', { method: 'POST', body: JSON.stringify(dados) }),
  editar:  (id, d) => req(`/${id}`, { method: 'PUT', body: JSON.stringify(d) }),
  excluir: (id)    => req(`/${id}`, { method: 'DELETE' }),
}
