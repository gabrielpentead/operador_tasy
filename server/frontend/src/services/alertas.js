/**
 * Chamadas de gerenciamento dos destinatários de alertas críticos.
 * Usam o cookie de sessão (credentials:'include') — as rotas são admin.
 */
const base = '/api/alertas'

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

export const alertasApi = {
  listar:  ()        => req('/destinatarios'),
  criar:   (dados)   => req('/destinatarios', { method: 'POST', body: JSON.stringify(dados) }),
  editar:  (id, d)   => req(`/destinatarios/${id}`, { method: 'PUT', body: JSON.stringify(d) }),
  excluir: (id)      => req(`/destinatarios/${id}`, { method: 'DELETE' }),
  testar:  ()        => req('/testar', { method: 'POST' }),
}
