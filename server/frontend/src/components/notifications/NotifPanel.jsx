import { forwardRef } from 'react'
import { useNotificacoes } from '../../context/NotificacoesContext'
import { notifRelTime } from '../../utils/format'

/** Ícone e cor por tipo — mesmos mapas de _notifIcon() e _notifColor(). */
const ICONES = {
  offline: 'bi-wifi-off',
  online: 'bi-wifi',
  health_atencao: 'bi-exclamation-triangle-fill',
  health_critico: 'bi-exclamation-octagon-fill',
}
const CORES = {
  offline: 'notif-color-danger',
  online: 'notif-color-success',
  health_atencao: 'notif-color-warning',
  health_critico: 'notif-color-danger',
}

const NotifPanel = forwardRef(function NotifPanel({ aberto }, ref) {
  const { lista, marcarLida, marcarTodasLidas, limparTodas } = useNotificacoes()

  return (
    <div
      ref={ref}
      className={`notif-panel${aberto ? ' notif-open' : ''}`}
      role="dialog"
      aria-label="Notificações"
    >
      <div className="notif-panel-header">
        <span className="notif-panel-title">
          <i className="bi bi-bell-fill me-2" />Notificações
        </span>
        <div className="notif-panel-actions">
          <button
            className="notif-action-btn"
            onClick={marcarTodasLidas}
            title="Marcar todas como lidas"
          >
            <i className="bi bi-check2-all" />
          </button>
          <button
            className="notif-action-btn notif-action-btn-danger"
            onClick={limparTodas}
            title="Limpar todas"
          >
            <i className="bi bi-trash3" />
          </button>
        </div>
      </div>

      <div className="notif-list">
        {lista.map((n) => (
          <div
            key={n.id}
            className={`notif-item ${n.read ? 'notif-read' : 'notif-unread'}`}
            onClick={() => marcarLida(n.id)}
          >
            <div className={`notif-item-icon ${CORES[n.type] || 'notif-color-info'}`}>
              <i className={`bi ${ICONES[n.type] || 'bi-bell-fill'}`} />
            </div>
            <div className="notif-item-body">
              <div className="notif-item-title">{n.title}</div>
              <div className="notif-item-msg">{n.message}</div>
              <div className="notif-item-time">
                <i className="bi bi-clock me-1" />{notifRelTime(n.timestamp)}
              </div>
            </div>
            {!n.read && <span className="notif-dot" />}
          </div>
        ))}
      </div>

      <div className={`notif-empty${lista.length ? ' d-none' : ''}`}>
        <i className="bi bi-bell-slash" />
        <span>Sem notificações</span>
      </div>
    </div>
  )
})

export default NotifPanel
