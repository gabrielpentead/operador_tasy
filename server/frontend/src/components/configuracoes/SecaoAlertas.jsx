import { useState, useEffect, useCallback } from 'react'
import ModalDestinatario from '../modals/ModalDestinatario'
import ModalConfirmarExclusao from '../modals/ModalConfirmarExclusao'
import { useToast } from '../../context/ToastContext'
import { alertasApi } from '../../services/alertas'

/**
 * Seção "Alertas" das Configurações — cadastro de quem recebe os alertas
 * críticos por e-mail (queda geral / Tasy indisponível). Só admin.
 *
 * A detecção em si é automática no servidor; aqui é só a lista de destinatários.
 */
export default function SecaoAlertas() {
  const { mostrarNotificacao } = useToast()

  const [lista, setLista] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [modal, setModal] = useState({ aberto: false, destinatario: null })
  const [exclusao, setExclusao] = useState({ aberto: false, destinatario: null })
  const [testando, setTestando] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    const r = await alertasApi.listar()
    if (r.ok && r.success) setLista(r.destinatarios)
    else mostrarNotificacao(r.error || 'Não foi possível carregar os destinatários', 'danger')
    setCarregando(false)
  }, [mostrarNotificacao])

  useEffect(() => { carregar() }, [carregar])

  const salvar = async (dados) => {
    const r = modal.destinatario
      ? await alertasApi.editar(modal.destinatario.id, dados)
      : await alertasApi.criar(dados)
    if (r.ok && r.success) {
      mostrarNotificacao(modal.destinatario ? 'Destinatário atualizado' : 'Destinatário adicionado', 'success')
      setModal({ aberto: false, destinatario: null })
      carregar()
      return {}
    }
    return { erro: r.error || 'Não foi possível salvar' }
  }

  const alternar = async (d, campo) => {
    const r = await alertasApi.editar(d.id, { [campo]: !d[campo] })
    if (r.ok && r.success) carregar()
    else mostrarNotificacao(r.error || 'Não foi possível alterar', 'danger')
  }

  const excluir = async () => {
    const r = await alertasApi.excluir(exclusao.destinatario.id)
    if (r.ok && r.success) {
      mostrarNotificacao('Destinatário removido', 'success')
      carregar()
    } else {
      mostrarNotificacao(r.error || 'Não foi possível remover', 'danger')
    }
    setExclusao({ aberto: false, destinatario: null })
  }

  const testar = async () => {
    setTestando(true)
    const r = await alertasApi.testar()
    setTestando(false)
    if (r.ok && r.success) mostrarNotificacao(r.mensagem || 'E-mail de teste enviado', 'success')
    else mostrarNotificacao(r.error || 'Não foi possível enviar o teste', 'danger')
  }

  return (
    <>
      <div className="secao-cabecalho">
        <div>
          <h5 className="secao-titulo">Alertas críticos</h5>
          <p className="secao-descricao">
            Quem recebe os e-mails quando o sistema detecta uma possível falha geral
            (vários painéis reiniciando / Tasy indisponível).
          </p>
        </div>
        <div className="d-flex gap-2">
          <button className="btn btn-outline-secondary" onClick={testar} disabled={testando}>
            {testando
              ? <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Enviando…</>
              : <><i className="bi bi-send me-2" />Enviar teste</>}
          </button>
          <button className="btn btn-primary" onClick={() => setModal({ aberto: true, destinatario: null })}>
            <i className="bi bi-envelope-plus me-2" />Novo destinatário
          </button>
        </div>
      </div>

      <div className="card border-0 shadow-sm">
        <div className="card-body p-0">
          {carregando ? (
            <div className="text-center py-5">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Carregando…</span>
              </div>
              <p className="mt-2 mb-0 text-muted">Carregando destinatários…</p>
            </div>
          ) : (
            <div className="table-responsive tabela-usuarios">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Nome</th>
                    <th>E-mail</th>
                    <th>Status</th>
                    <th className="celula-acoes">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {lista.map((d) => (
                    <tr key={d.id}>
                      <td data-rotulo="Nome">
                        {d.nome
                          ? <span className="fw-semibold">{d.nome}</span>
                          : <span className="text-muted fst-italic">—</span>}
                      </td>
                      <td className="small" data-rotulo="E-mail">{d.email}</td>
                      <td data-rotulo="Status">
                        {d.ativo
                          ? <span className="badge bg-success"><i className="bi bi-bell-fill me-1" />Recebendo</span>
                          : <span className="badge bg-secondary">Pausado</span>}
                      </td>
                      <td className="celula-acoes" data-rotulo="Ações">
                        <div className="btn-group btn-group-sm">
                          <button className="btn btn-outline-primary" title="Editar"
                                  onClick={() => setModal({ aberto: true, destinatario: d })}>
                            <i className="bi bi-pencil" />
                          </button>
                          <button className={`btn btn-outline-${d.ativo ? 'warning' : 'success'}`}
                                  title={d.ativo ? 'Pausar' : 'Ativar'}
                                  onClick={() => alternar(d, 'ativo')}>
                            <i className={`bi bi-${d.ativo ? 'pause' : 'play'}-fill`} />
                          </button>
                          <button className="btn btn-outline-danger" title="Remover"
                                  onClick={() => setExclusao({ aberto: true, destinatario: d })}>
                            <i className="bi bi-trash" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {lista.length === 0 && (
                    <tr>
                      <td colSpan="4" className="text-center text-muted py-4">
                        Nenhum destinatário cadastrado. Adicione ao menos um para receber os alertas.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <ModalDestinatario
        aberto={modal.aberto}
        destinatario={modal.destinatario}
        onFechar={() => setModal({ aberto: false, destinatario: null })}
        onSalvar={salvar}
      />

      <ModalConfirmarExclusao
        aberto={exclusao.aberto}
        onFechar={() => setExclusao({ aberto: false, destinatario: null })}
        onConfirmar={excluir}
        mensagem={<>Remover <strong>{exclusao.destinatario?.email}</strong> da lista de alertas?</>}
      />
    </>
  )
}
