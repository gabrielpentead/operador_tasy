import { useState, useEffect } from 'react'
import Modal from './Modal'
import { LOGIN_MAX, SENHA_MAX, SENHA_MIN } from '../../config/constants'

/**
 * Criação e edição de usuário. Mesma base de modal e mesmas classes de
 * formulário do ModalOperador, para o visual não destoar.
 *
 * Na edição, o campo de senha fica vazio e só é enviado se preenchido — assim
 * editar o nome de alguém não força a redefinir a senha dessa pessoa.
 */
export default function ModalUsuario({ aberto, onFechar, onSalvar, usuario, souEu }) {
  const editando = Boolean(usuario)

  const [nome, setNome] = useState('')
  const [login, setLogin] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [role, setRole] = useState('operador')
  const [ativo, setAtivo] = useState(true)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    if (!aberto) return
    setNome(usuario?.nome || '')
    setLogin(usuario?.login || '')
    setEmail(usuario?.email || '')
    setSenha('')
    setRole(usuario?.role || 'operador')
    setAtivo(usuario ? usuario.ativo : true)
    setErro('')
    setSalvando(false)
  }, [aberto, usuario])

  const salvar = async () => {
    if (!nome.trim() || !login.trim()) {
      setErro('Nome e usuário são obrigatórios')
      return
    }
    // E-mail é exigido no cadastro porque será a chave da redefinição de senha.
    if (!editando && !email.trim()) {
      setErro('Informe o e-mail do usuário')
      return
    }
    if (email.trim() && !/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(email.trim())) {
      setErro('E-mail inválido')
      return
    }
    if (login.trim().length > LOGIN_MAX) {
      setErro(`O usuário deve ter no máximo ${LOGIN_MAX} caracteres`)
      return
    }
    if (!editando && senha.length < SENHA_MIN) {
      setErro(`A senha precisa ter ao menos ${SENHA_MIN} caracteres`)
      return
    }
    if (editando && senha && senha.length < SENHA_MIN) {
      setErro(`A nova senha precisa ter ao menos ${SENHA_MIN} caracteres`)
      return
    }
    if (senha && senha.length > SENHA_MAX) {
      setErro(`A senha deve ter no máximo ${SENHA_MAX} caracteres`)
      return
    }

    setSalvando(true)
    setErro('')
    const dados = { nome: nome.trim(), login: login.trim(), email: email.trim(), role, ativo }
    if (senha) dados.senha = senha

    const r = await onSalvar(dados)
    if (r?.erro) {
      setErro(r.erro)
      setSalvando(false)
    }
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={editando ? 'Editar Usuário' : 'Novo Usuário'}
      icone={editando ? 'bi-pencil-square' : 'bi-person-plus'}
      rodape={
        <>
          <button type="button" className="btn btn-secondary" onClick={onFechar} disabled={salvando}>
            Cancelar
          </button>
          <button type="button" className="btn btn-primary" onClick={salvar} disabled={salvando}>
            {salvando ? (
              <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Salvando…</>
            ) : (editando ? 'Salvar Alterações' : 'Criar Usuário')}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label htmlFor="usr-nome" className="form-label">Nome</label>
        <input id="usr-nome" type="text" className="form-control" value={nome}
               onChange={(e) => { setNome(e.target.value); setErro('') }} />
      </div>

      <div className="mb-3">
        <label htmlFor="usr-login" className="form-label">Usuário (login)</label>
        <input id="usr-login" type="text" className="form-control" value={login}
               autoComplete="off" maxLength={LOGIN_MAX}
               onChange={(e) => { setLogin(e.target.value.slice(0, LOGIN_MAX)); setErro('') }} />
        <div className="form-text">{login.length}/{LOGIN_MAX} caracteres</div>
      </div>

      <div className="mb-3">
        <label htmlFor="usr-email" className="form-label">E-mail</label>
        <input id="usr-email" type="email" className="form-control" value={email}
               autoComplete="off" placeholder="nome@hospitalsaovicente.org.br"
               onChange={(e) => { setEmail(e.target.value); setErro('') }} />
        <div className="form-text">Usado para redefinir a senha.</div>
      </div>

      <div className="mb-3">
        <label htmlFor="usr-senha" className="form-label">
          {editando ? 'Nova senha' : 'Senha'}
          {editando && <span className="text-muted small ms-2">(deixe vazio para manter a atual)</span>}
        </label>
        <input id="usr-senha" type="password" className="form-control" value={senha}
               autoComplete="new-password" maxLength={SENHA_MAX}
               onChange={(e) => { setSenha(e.target.value.slice(0, SENHA_MAX)); setErro('') }} />
        <div className="form-text">
          {senha.length}/{SENHA_MAX} caracteres — mínimo {SENHA_MIN}
        </div>
      </div>

      <hr />

      <div className="mb-3">
        <label htmlFor="usr-role" className="form-label">Permissão</label>
        <select id="usr-role" className="form-select" value={role}
                disabled={souEu}
                onChange={(e) => { setRole(e.target.value); setErro('') }}>
          <option value="operador">Operador — acessa o painel</option>
          <option value="admin">Administrador — acessa tudo, inclusive usuários</option>
        </select>
        {souEu && (
          <div className="form-text">
            Você não pode alterar a própria permissão.
          </div>
        )}
      </div>

      <div className="form-check form-switch mb-3">
        <input className="form-check-input" type="checkbox" id="usr-ativo"
               checked={ativo} disabled={souEu}
               onChange={(e) => { setAtivo(e.target.checked); setErro('') }} />
        <label className="form-check-label" htmlFor="usr-ativo">
          Usuário ativo
        </label>
        {souEu && (
          <div className="form-text">Você não pode desativar a própria conta.</div>
        )}
      </div>

      {erro && (
        <div className="alert alert-danger py-2 mb-0" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2" />{erro}
        </div>
      )}
    </Modal>
  )
}
