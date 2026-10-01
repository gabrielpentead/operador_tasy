import Modal from './Modal'
import { getAutomationStatus } from '../../utils/status'

/**
 * Porte de prepararComando() para o tipo "Ambos".
 *
 * Regras de habilitação dos botões preservadas literalmente:
 *  - iniciar:   desabilita o alvo que JÁ está rodando
 *  - parar:     desabilita o alvo que NÃO está rodando
 *  - reiniciar: todos sempre habilitados
 */
export default function ModalConfirmarAcao({ aberto, operador, comando, onFechar, onEscolher }) {
  if (!operador) return null

  const st = getAutomationStatus(operador)

  let monitorDisabled = false
  let totemDisabled = false
  let ambosDisabled = false

  if (comando === 'iniciar') {
    monitorDisabled = st.monitor.isRunning
    totemDisabled = st.totem.isRunning
    ambosDisabled = st.monitor.isRunning && st.totem.isRunning
  } else if (comando === 'parar') {
    monitorDisabled = !st.monitor.isRunning
    totemDisabled = !st.totem.isRunning
    ambosDisabled = !st.monitor.isRunning && !st.totem.isRunning
  }

  const titulo = comando
    ? `Confirmar Ação: ${comando.charAt(0).toUpperCase()}${comando.slice(1)}`
    : 'Confirmar Ação'

  const rodape = (
    <button type="button" className="btn btn-secondary" onClick={onFechar}>Cancelar</button>
  )

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={titulo}
      icone="bi-question-circle"
      rodape={rodape}
    >
      <p>
        Para qual parte do operador <strong>{operador.nome}</strong> você deseja enviar o comando?
      </p>
      <div className="d-grid gap-2">
        <button
          type="button" className="btn btn-outline-primary"
          disabled={monitorDisabled} onClick={() => onEscolher('monitor')}
        >
          <i className="bi bi-display" /> Apenas Monitor
        </button>
        <button
          type="button" className="btn btn-outline-primary"
          disabled={totemDisabled} onClick={() => onEscolher('totem')}
        >
          <i className="bi bi-printer" /> Apenas Totem
        </button>
        <button
          type="button" className="btn btn-primary"
          disabled={ambosDisabled} onClick={() => onEscolher('ambos')}
        >
          <i className="bi bi-collection" /> Ambos
        </button>
      </div>
    </Modal>
  )
}
