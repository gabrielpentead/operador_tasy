import { useState, useEffect } from 'react'
import Modal from './Modal'

/**
 * Modais de Adicionar e Editar operador.
 *
 * Porte de salvarOperador() e abrirModalEdicao(). Regras preservadas:
 *  - Adicionar: nome, descrição, usuário, senha, tipo de cadastro
 *  - Editar: acrescenta o switch de credenciais separadas, visível apenas
 *    quando o tipo é "Ambos" (porte de toggleCredentialFields)
 *  - com credenciais separadas, username/password principais recebem os do
 *    monitor como fallback, exatamente como no original
 *  - validação: apenas o nome é obrigatório no envio
 */

const TIPOS = [
  { valor: 'Monitor de Senhas', rotulo: 'Monitor de Senhas (TV)' },
  { valor: 'Totem de Senhas', rotulo: 'Totem de Senhas (Chamada)' },
  { valor: 'Ambos', rotulo: 'Ambos (Monitor e Totem)' },
]

const VAZIO = {
  nome: '', descricao: '', tipo_cadastro: 'Monitor de Senhas',
  username: '', password: '',
  usa_credenciais_separadas: false,
  username_monitor: '', password_monitor: '',
  username_totem: '', password_totem: '',
}

export default function ModalOperador({ aberto, modo, operador, onFechar, onSalvar }) {
  const isEdit = modo === 'editar'
  const [form, setForm] = useState(VAZIO)

  useEffect(() => {
    if (!aberto) return
    if (isEdit && operador) {
      setForm({
        nome: operador.nome || '',
        descricao: operador.descricao || '',
        tipo_cadastro: operador.tipo_cadastro || 'Monitor de Senhas',
        username: operador.username || '',
        password: operador.password || '',
        usa_credenciais_separadas: operador.usa_credenciais_separadas || false,
        username_monitor: operador.username_monitor || '',
        password_monitor: operador.password_monitor || '',
        username_totem: operador.username_totem || '',
        password_totem: operador.password_totem || '',
      })
    } else {
      setForm(VAZIO)
    }
  }, [aberto, isEdit, operador])

  const set = (campo) => (e) => {
    const valor = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  // Credenciais separadas só valem para "Ambos" — mesma regra do original
  const mostrarSeparadas = form.tipo_cadastro === 'Ambos' && form.usa_credenciais_separadas

  const submeter = () => {
    const payload = {
      nome: form.nome,
      descricao: form.descricao,
      tipo_cadastro: form.tipo_cadastro,
      usa_credenciais_separadas: false,
    }

    if (form.tipo_cadastro === 'Ambos' && form.usa_credenciais_separadas) {
      payload.usa_credenciais_separadas = true
      payload.username_monitor = form.username_monitor
      payload.password_monitor = form.password_monitor
      payload.username_totem = form.username_totem
      payload.password_totem = form.password_totem
      // Fallback para as credenciais principais, igual ao original
      payload.username = form.username_monitor
      payload.password = form.password_monitor
    } else {
      payload.username = form.username
      payload.password = form.password
    }

    onSalvar(payload)
  }

  const rodape = (
    <>
      <button type="button" className="btn btn-secondary" onClick={onFechar}>Cancelar</button>
      <button type="button" className="btn btn-primary" onClick={submeter}>
        {isEdit ? 'Salvar Alterações' : 'Salvar'}
      </button>
    </>
  )

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={isEdit ? 'Editar Operador' : 'Adicionar Novo Operador'}
      icone={isEdit ? 'bi-pencil-square' : 'bi-plus-circle'}
      rodape={rodape}
    >
      <form onSubmit={(e) => e.preventDefault()}>
        <div className="mb-3">
          <label className="form-label">Nome do Operador</label>
          <input type="text" className="form-control" value={form.nome} onChange={set('nome')} required />
        </div>
        <div className="mb-3">
          <label className="form-label">Descrição</label>
          <textarea className="form-control" rows="2" value={form.descricao} onChange={set('descricao')} />
        </div>

        {!isEdit && (
          <>
            <div className="mb-3">
              <label className="form-label">Nome de Usuário</label>
              <input type="text" className="form-control" value={form.username} onChange={set('username')} required />
            </div>
            <div className="mb-3">
              <label className="form-label">Senha</label>
              <input type="password" className="form-control" value={form.password} onChange={set('password')} required />
            </div>
          </>
        )}

        <div className="mb-3">
          <label className="form-label">Tipo de Cadastro</label>
          <select
            className="form-select"
            value={form.tipo_cadastro}
            onChange={set('tipo_cadastro')}
            required
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>{t.rotulo}</option>
            ))}
          </select>
        </div>

        {isEdit && (
          <>
            <hr />
            <div>
              <div className="form-check form-switch mb-3">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="edit-usa_credenciais_separadas"
                  checked={form.usa_credenciais_separadas}
                  onChange={set('usa_credenciais_separadas')}
                  disabled={form.tipo_cadastro !== 'Ambos'}
                />
                <label className="form-check-label" htmlFor="edit-usa_credenciais_separadas">
                  Usar credenciais diferentes para Monitor e Totem
                </label>
              </div>

              {!mostrarSeparadas && (
                <>
                  <div className="mb-3">
                    <label className="form-label">Nome de Usuário (Compartilhado)</label>
                    <input type="text" className="form-control" value={form.username} onChange={set('username')} />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Senha (Compartilhada)</label>
                    <input type="password" className="form-control" value={form.password} onChange={set('password')} />
                  </div>
                </>
              )}

              {mostrarSeparadas && (
                <>
                  <h6 className="mt-4">Credenciais do Monitor</h6>
                  <div className="mb-3">
                    <label className="form-label">Usuário do Monitor</label>
                    <input type="text" className="form-control" value={form.username_monitor} onChange={set('username_monitor')} />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Senha do Monitor</label>
                    <input type="password" className="form-control" value={form.password_monitor} onChange={set('password_monitor')} />
                  </div>

                  <h6 className="mt-4">Credenciais do Totem</h6>
                  <div className="mb-3">
                    <label className="form-label">Usuário do Totem</label>
                    <input type="text" className="form-control" value={form.username_totem} onChange={set('username_totem')} />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Senha do Totem</label>
                    <input type="password" className="form-control" value={form.password_totem} onChange={set('password_totem')} />
                  </div>
                </>
              )}
            </div>
            <hr />
          </>
        )}
      </form>
    </Modal>
  )
}
