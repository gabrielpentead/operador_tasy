import { useState, useEffect, useCallback } from 'react'
import ModalUsuario from '../modals/ModalUsuario'
import ModalConfirmarExclusao from '../modals/ModalConfirmarExclusao'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { authApi } from '../../services/auth'

/**
 * Seção "Usuários" das Configurações. Só administradores chegam aqui — o App
 * bloqueia a navegação e o servidor recusa as chamadas com 403, então esconder
 * botões é apenas conveniência, não o controle em si.
 */
export default function SecaoUsuarios() {
  const { usuario: eu } = useAuth()
  const { mostrarNotificacao } = useToast()

  const [usuarios, setUsuarios] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [modal, setModal] = useState({ aberto: false, usuario: null })
  const [exclusao, setExclusao] = useState({ aberto: false, usuario: null })
  const [redefinindo, setRedefinindo] = useState(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    const r = await authApi.listarUsuarios()
    if (r.ok && r.success) setUsuarios(r.usuarios)
    else mostrarNotificacao(r.error || 'Não foi possível carregar os usuários', 'danger')
    setCarregando(false)
  }, [mostrarNotificacao])

  useEffect(() => { carregar() }, [carregar])

  const salvar = async (dados) => {
    const r = modal.usuario
      ? await authApi.editarUsuario(modal.usuario.id, dados)
      : await authApi.criarUsuario(dados)

    if (r.ok && r.success) {
      mostrarNotificacao(modal.usuario ? 'Usuário atualizado' : 'Usuário criado', 'success')
      setModal({ aberto: false, usuario: null })
      carregar()
      return {}
    }
    return { erro: r.error || 'Não foi possível salvar' }
  }

  const alternarAtivo = async (u) => {
    const r = await authApi.editarUsuario(u.id, { ativo: !u.ativo })
    if (r.ok && r.success) {
      mostrarNotificacao(u.ativo ? 'Usuário desativado' : 'Usuário ativado', 'success')
      carregar()
    } else {
      mostrarNotificacao(r.error || 'Não foi possível alterar o status', 'danger')
    }
  }

  const redefinirSenha = async (u) => {
    if (!u.email) {
      mostrarNotificacao('Cadastre um e-mail para este usuário antes de redefinir a senha.', 'warning')
      return
    }
    setRedefinindo(u.id)
    const r = await authApi.redefinirSenha(u.id)
    setRedefinindo(null)
    if (r.ok && r.success) mostrarNotificacao(r.mensagem || 'Nova senha enviada por e-mail', 'success')
    else mostrarNotificacao(r.error || 'Não foi possível redefinir a senha', 'danger')
  }

  const excluir = async () => {
    const r = await authApi.excluirUsuario(exclusao.usuario.id)
    if (r.ok && r.success) {
      mostrarNotificacao('Usuário excluído', 'success')
      setExclusao({ aberto: false, usuario: null })
      carregar()
    } else {
      mostrarNotificacao(r.error || 'Não foi possível excluir', 'danger')
      setExclusao({ aberto: false, usuario: null })
    }
  }

  const formatarData = (iso) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return iso }
  }

  return (
    <>
      <div className="secao-cabecalho">
        <div>
          <h5 className="secao-titulo">Usuários</h5>
          <p className="secao-descricao">Quem pode acessar o painel e com quais permissões.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ aberto: true, usuario: null })}>
          <i className="bi bi-person-plus me-2" />Novo Usuário
        </button>
      </div>

        <div className="card border-0 shadow-sm">
          <div className="card-body p-0">
            {carregando ? (
              <div className="text-center py-5">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Carregando…</span>
                </div>
                <p className="mt-2 mb-0 text-muted">Carregando usuários…</p>
              </div>
            ) : (
              <div className="table-responsive tabela-usuarios">
                <table className="table table-hover align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Nome</th>
                      <th>Usuário</th>
                      <th>E-mail</th>
                      <th>Permissão</th>
                      <th>Status</th>
                      <th>Último acesso</th>
                      <th className="celula-acoes">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuarios.map((u) => {
                      const souEu = u.id === eu?.id
                      return (
                        <tr key={u.id}>
                          <td data-rotulo="Nome">
                            <span className="fw-semibold">{u.nome}</span>
                            {souEu && <span className="badge bg-secondary ms-2">você</span>}
                          </td>
                          <td data-rotulo="Usuário"><code>{u.login}</code></td>
                          <td className="small" data-rotulo="E-mail">
                            {u.email
                              ? <span className="text-body" title={u.email}>{u.email}</span>
                              : <span className="text-muted fst-italic">não informado</span>}
                          </td>
                          <td data-rotulo="Permissão">
                            {u.role === 'admin' ? (
                              <span className="badge bg-primary">
                                <i className="bi bi-shield-lock me-1" />Administrador
                              </span>
                            ) : (
                              <span className="badge bg-secondary">
                                <i className="bi bi-person me-1" />Operador
                              </span>
                            )}
                          </td>
                          <td data-rotulo="Status">
                            {u.ativo
                              ? <span className="badge bg-success">Ativo</span>
                              : <span className="badge bg-danger">Inativo</span>}
                          </td>
                          <td className="text-muted small" data-rotulo="Último acesso">{formatarData(u.ultimo_acesso)}</td>
                          <td className="celula-acoes" data-rotulo="Ações">
                            <div className="btn-group btn-group-sm">
                              <button className="btn btn-outline-primary" title="Editar"
                                      onClick={() => setModal({ aberto: true, usuario: u })}>
                                <i className="bi bi-pencil" />
                              </button>
                              <button className="btn btn-outline-secondary"
                                      title={u.email ? 'Redefinir senha e enviar por e-mail'
                                                     : 'Cadastre um e-mail primeiro'}
                                      disabled={!u.email || redefinindo === u.id}
                                      onClick={() => redefinirSenha(u)}>
                                {redefinindo === u.id
                                  ? <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                                  : <i className="bi bi-key" />}
                              </button>
                              <button
                                className={`btn btn-outline-${u.ativo ? 'warning' : 'success'}`}
                                title={u.ativo ? 'Desativar' : 'Ativar'}
                                disabled={souEu}
                                onClick={() => alternarAtivo(u)}>
                                <i className={`bi bi-${u.ativo ? 'pause' : 'play'}-fill`} />
                              </button>
                              <button className="btn btn-outline-danger" title="Excluir"
                                      disabled={souEu}
                                      onClick={() => setExclusao({ aberto: true, usuario: u })}>
                                <i className="bi bi-trash" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                    {usuarios.length === 0 && (
                      <tr>
                        <td colSpan="7" className="text-center text-muted py-4">
                          Nenhum usuário cadastrado
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>


      <ModalUsuario
        aberto={modal.aberto}
        usuario={modal.usuario}
        souEu={modal.usuario?.id === eu?.id}
        onFechar={() => setModal({ aberto: false, usuario: null })}
        onSalvar={salvar}
      />

      <ModalConfirmarExclusao
        aberto={exclusao.aberto}
        operador={exclusao.usuario}
        onFechar={() => setExclusao({ aberto: false, usuario: null })}
        onConfirmar={excluir}
      />
    </>
  )
}
