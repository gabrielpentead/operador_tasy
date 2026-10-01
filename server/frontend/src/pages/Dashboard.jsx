import { useState, useMemo, useCallback, useRef } from 'react'
import { useOperadores } from '../context/OperadoresContext'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import * as api from '../services/api'

import StatusCards from '../components/dashboard/StatusCards'
import ServerHealthCard from '../components/dashboard/ServerHealthCard'
import OperadorCard from '../components/dashboard/OperadorCard'
import ModalOperador from '../components/modals/ModalOperador'
import ModalConfirmarExclusao from '../components/modals/ModalConfirmarExclusao'
import ModalConfirmarAcao from '../components/modals/ModalConfirmarAcao'

/**
 * Página única do sistema — equivalente ao index.html + dashboard.js.
 *
 * O filtro de texto continua comparando nome e descrição em minúsculas,
 * exatamente como filtrarOperadores() fazia via dataset.
 */
export default function Dashboard() {
  const { operadores, carregando, carregarOperadores } = useOperadores()
  const { mostrarNotificacao } = useToast()

  const [filtro, setFiltro] = useState('')
  const { isAdmin } = useAuth()
  const [modalOperador, setModalOperador] = useState({ aberto: false, modo: 'adicionar', dados: null })
  const [modalExclusao, setModalExclusao] = useState({ aberto: false, operador: null })
  const [modalAcao, setModalAcao] = useState({ aberto: false, operador: null, comando: null })

  // Callback pendente do fluxo de revelar senha

  const filtrados = useMemo(() => {
    const f = filtro.toLowerCase()
    if (!f) return operadores
    return operadores.filter((op) => {
      const nome = (op.nome || '').toLowerCase()
      const descricao = (op.descricao || '').toLowerCase()
      return nome.includes(f) || descricao.includes(f)
    })
  }, [operadores, filtro])

  /* ── Comandos ────────────────────────────────────────────────── */
  const enviarComando = useCallback(
    async (operadorId, comando, target = 'ambos') => {
      try {
        const data = await api.enviarComando(operadorId, comando, target)
        mostrarNotificacao(
          data.success ? `Comando '${comando}' enviado.` : `Erro: ${data.error}`,
          data.success ? 'success' : 'danger'
        )
      } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger')
      }
    },
    [mostrarNotificacao]
  )

  const prepararComando = useCallback(
    (operador, comando) => {
      // Tipo "Ambos" pergunta o alvo; os demais vão direto, igual ao original
      if (operador.tipo_cadastro === 'Ambos') {
        setModalAcao({ aberto: true, operador, comando })
      } else {
        enviarComando(operador.id, comando, 'ambos')
      }
    },
    [enviarComando]
  )

  /* ── CRUD ────────────────────────────────────────────────────── */
  const abrirEdicao = useCallback(
    async (operadorId) => {
      try {
        const data = await api.obterOperador(operadorId)
        if (data.success) {
          setModalOperador({ aberto: true, modo: 'editar', dados: data.operador })
        } else {
          mostrarNotificacao(`Erro ao carregar operador: ${data.error}`, 'danger')
        }
      } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger')
      }
    },
    [mostrarNotificacao]
  )

  const salvarOperador = useCallback(
    async (payload) => {
      if (!payload.nome) {
        mostrarNotificacao('O nome do operador é obrigatório.', 'danger')
        return
      }
      const isEdit = modalOperador.modo === 'editar'
      try {
        const data = isEdit
          ? await api.atualizarOperador(modalOperador.dados.id, payload)
          : await api.criarOperador(payload)

        if (data.success) {
          setModalOperador({ aberto: false, modo: 'adicionar', dados: null })
          mostrarNotificacao(`Operador ${isEdit ? 'atualizado' : 'adicionado'}.`, 'success')
          carregarOperadores()
        } else {
          mostrarNotificacao(`Erro: ${data.error}`, 'danger')
        }
      } catch (error) {
        mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger')
      }
    },
    [modalOperador, mostrarNotificacao, carregarOperadores]
  )

  const confirmarExclusao = useCallback(async () => {
    const op = modalExclusao.operador
    if (!op) return
    try {
      const data = await api.excluirOperador(op.id)
      if (data.success) {
        setModalExclusao({ aberto: false, operador: null })
        mostrarNotificacao('Operador excluído', 'success')
        carregarOperadores()
      } else {
        mostrarNotificacao(`Erro ao excluir: ${data.error}`, 'danger')
      }
    } catch (error) {
      mostrarNotificacao(`Erro de conexão: ${error.message}`, 'danger')
    }
  }, [modalExclusao, mostrarNotificacao, carregarOperadores])

  return (
    <div className="container">
      <StatusCards />
      <ServerHealthCard />

      <div className="mb-4">
        <div className="input-group">
          <span className="input-group-text"><i className="bi bi-search" /></span>
          <input
            type="text"
            className="form-control"
            placeholder="Filtrar operadores..."
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
          />
        </div>
      </div>

      <div className="row operadores-grid">
        {carregando && (
          <div className="col-12 text-center py-5">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Carregando...</span>
            </div>
            <p className="mt-2">Carregando operadores...</p>
          </div>
        )}

        {!carregando && filtrados.map((op) => (
          <div className="col-md-6 col-lg-4 mb-4 operador-item" key={op.id}>
            <OperadorCard
              operador={op}
              onComando={prepararComando}
              onEditar={abrirEdicao}
              onExcluir={(o) => setModalExclusao({ aberto: true, operador: o })}
              podeAdministrar={isAdmin}
            />
          </div>
        ))}
      </div>

      {!carregando && operadores.length === 0 && (
        <div className="text-center py-5">
          <i className="bi bi-exclamation-circle text-muted" style={{ fontSize: '3rem' }} />
          <h4 className="mt-3">Nenhum operador cadastrado</h4>
          <p className="text-muted">
            {isAdmin
              ? 'Adicione um operador para começar a utilizar o sistema'
              : 'Nenhum operador foi cadastrado ainda. Procure um administrador.'}
          </p>
          {isAdmin && (
            <button
              className="btn btn-primary mt-2"
              onClick={() => setModalOperador({ aberto: true, modo: 'adicionar', dados: null })}
            >
              <i className="bi bi-plus-circle" /> Adicionar Operador
            </button>
          )}
        </div>
      )}

      <footer className="mt-5 pt-4 pb-2 text-center text-muted">
        <p className="small">NTI - Núcleo de Tecnologia da Informação</p>
      </footer>

      {/* ── Modais ── */}
      <ModalOperador
        aberto={modalOperador.aberto}
        modo={modalOperador.modo}
        operador={modalOperador.dados}
        onFechar={() => setModalOperador({ aberto: false, modo: 'adicionar', dados: null })}
        onSalvar={salvarOperador}
      />

      <ModalConfirmarExclusao
        aberto={modalExclusao.aberto}
        operador={modalExclusao.operador}
        onFechar={() => setModalExclusao({ aberto: false, operador: null })}
        onConfirmar={confirmarExclusao}
      />

      <ModalConfirmarAcao
        aberto={modalAcao.aberto}
        operador={modalAcao.operador}
        comando={modalAcao.comando}
        onFechar={() => setModalAcao({ aberto: false, operador: null, comando: null })}
        onEscolher={(target) => {
          enviarComando(modalAcao.operador.id, modalAcao.comando, target)
          setModalAcao({ aberto: false, operador: null, comando: null })
        }}
      />

    </div>
  )
}
