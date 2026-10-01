import { useState, useEffect, useCallback } from 'react'
import ModalReinicioProgramado from '../modals/ModalReinicioProgramado'
import ModalConfirmarExclusao from '../modals/ModalConfirmarExclusao'
import { useToast } from '../../context/ToastContext'
import { reiniciosApi } from '../../services/reinicios'

// Mesma convenção do agendador no servidor (Python weekday()): 0=segunda..6=domingo.
const NOMES_DIAS = { 0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom' }
const ORDEM_DIAS = [0, 1, 2, 3, 4, 5, 6]

function formatarDias(dias) {
  if (dias.length === 7) return 'Todos os dias'
  return ORDEM_DIAS.filter((d) => dias.includes(d)).map((d) => NOMES_DIAS[d]).join(', ')
}

const ROTULO_TARGET = { ambos: 'Ambos', monitor: 'Monitor', totem: 'Totem' }

/**
 * Seção "Reinícios" das Configurações — programação dos reinícios automáticos
 * dos painéis (Monitor/Totem). Só admin.
 *
 * O disparo em si acontece no servidor (monitoring/restart_scheduler.py);
 * aqui é só o cadastro dos horários.
 */
export default function SecaoReinicios() {
  const { mostrarNotificacao } = useToast()

  const [lista, setLista] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [modal, setModal] = useState({ aberto: false, reinicio: null })
  const [exclusao, setExclusao] = useState({ aberto: false, reinicio: null })

  const carregar = useCallback(async () => {
    setCarregando(true)
    const r = await reiniciosApi.listar()
    if (r.ok && r.success) setLista(r.reinicios)
    else mostrarNotificacao(r.error || 'Não foi possível carregar os reinícios programados', 'danger')
    setCarregando(false)
  }, [mostrarNotificacao])

  useEffect(() => { carregar() }, [carregar])

  const salvar = async (dados) => {
    const r = modal.reinicio
      ? await reiniciosApi.editar(modal.reinicio.id, dados)
      : await reiniciosApi.criar(dados)
    if (r.ok && r.success) {
      mostrarNotificacao(modal.reinicio ? 'Agendamento atualizado' : 'Agendamento criado', 'success')
      setModal({ aberto: false, reinicio: null })
      carregar()
      return {}
    }
    return { erro: r.error || 'Não foi possível salvar' }
  }

  const alternarAtivo = async (r) => {
    const resp = await reiniciosApi.editar(r.id, { ativo: !r.ativo })
    if (resp.ok && resp.success) carregar()
    else mostrarNotificacao(resp.error || 'Não foi possível alterar', 'danger')
  }

  const excluir = async () => {
    const r = await reiniciosApi.excluir(exclusao.reinicio.id)
    if (r.ok && r.success) {
      mostrarNotificacao('Agendamento removido', 'success')
      carregar()
    } else {
      mostrarNotificacao(r.error || 'Não foi possível remover', 'danger')
    }
    setExclusao({ aberto: false, reinicio: null })
  }

  return (
    <>
      <div className="secao-cabecalho">
        <div>
          <h5 className="secao-titulo">Reinícios automáticos</h5>
          <p className="secao-descricao">
            Horários em que o servidor envia o comando de reinício para os painéis
            conectados. Se um painel estiver offline no horário, ele simplesmente
            não recebe o comando e continua funcionando normalmente por conta própria.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ aberto: true, reinicio: null })}>
          <i className="bi bi-alarm-plus me-2" />Novo agendamento
        </button>
      </div>

      <div className="card border-0 shadow-sm">
        <div className="card-body p-0">
          {carregando ? (
            <div className="text-center py-5">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Carregando…</span>
              </div>
              <p className="mt-2 mb-0 text-muted">Carregando agendamentos…</p>
            </div>
          ) : (
            <div className="table-responsive tabela-usuarios">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Horário</th>
                    <th>Dias</th>
                    <th>Alvo</th>
                    <th>Status</th>
                    <th className="celula-acoes">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {lista.map((r) => (
                    <tr key={r.id}>
                      <td data-rotulo="Horário"><span className="fw-semibold">{r.horario}</span></td>
                      <td className="small" data-rotulo="Dias">
                        {formatarDias(r.dias_semana)}
                        {r.descricao && <div className="text-muted">{r.descricao}</div>}
                      </td>
                      <td data-rotulo="Alvo">{ROTULO_TARGET[r.target] || r.target}</td>
                      <td data-rotulo="Status">
                        {r.ativo
                          ? <span className="badge bg-success"><i className="bi bi-alarm-fill me-1" />Ativo</span>
                          : <span className="badge bg-secondary">Pausado</span>}
                      </td>
                      <td className="celula-acoes" data-rotulo="Ações">
                        <div className="btn-group btn-group-sm">
                          <button className="btn btn-outline-primary" title="Editar"
                                  onClick={() => setModal({ aberto: true, reinicio: r })}>
                            <i className="bi bi-pencil" />
                          </button>
                          <button className={`btn btn-outline-${r.ativo ? 'warning' : 'success'}`}
                                  title={r.ativo ? 'Pausar' : 'Ativar'}
                                  onClick={() => alternarAtivo(r)}>
                            <i className={`bi bi-${r.ativo ? 'pause' : 'play'}-fill`} />
                          </button>
                          <button className="btn btn-outline-danger" title="Remover"
                                  onClick={() => setExclusao({ aberto: true, reinicio: r })}>
                            <i className="bi bi-trash" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {lista.length === 0 && (
                    <tr>
                      <td colSpan="5" className="text-center text-muted py-4">
                        Nenhum reinício programado. Adicione um agendamento para os painéis
                        reiniciarem automaticamente.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <ModalReinicioProgramado
        aberto={modal.aberto}
        reinicio={modal.reinicio}
        onFechar={() => setModal({ aberto: false, reinicio: null })}
        onSalvar={salvar}
      />

      <ModalConfirmarExclusao
        aberto={exclusao.aberto}
        onFechar={() => setExclusao({ aberto: false, reinicio: null })}
        onConfirmar={excluir}
        mensagem={<>Remover o agendamento das <strong>{exclusao.reinicio?.horario}</strong>?</>}
      />
    </>
  )
}
