import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { getAutomationStatus } from '../../utils/status'
import ModalDetalheOperador from '../modals/ModalDetalheOperador'

/**
 * Card de operador (compacto). Mostra o essencial para acompanhamento rápido —
 * nome, online, hostname, tipo, usuário Tasy, senha, IP e o status detalhado da
 * automação. Clicar em qualquer parte do card abre o painel de detalhes
 * (ModalDetalheOperador) sobre o dashboard, com saúde, voz/idioma e versão.
 *
 * Nada da comunicação com o servidor mudou. As ações (iniciar/parar/reiniciar,
 * menu, revelar senha) usam stopPropagation para não abrir o detalhe ao clique.
 */

const TIPOS = {
  'Monitor de Senhas': {
    cardClass: 'tipo-monitor',
    icones: [{ src: '/static/img/monitor.png', title: 'Monitor de Senhas' }],
  },
  'Totem de Senhas': {
    cardClass: 'tipo-totem',
    icones: [{ src: '/static/img/totem.png', title: 'Totem de Senhas' }],
  },
  Ambos: {
    cardClass: 'tipo-ambos',
    icones: [
      { src: '/static/img/monitor.png', title: 'Monitor' },
      { src: '/static/img/totem.png', title: 'Totem' },
    ],
  },
}

function StatusDetalhes({ operador }) {
  if (!operador || !operador.online || !operador.status) {
    return (
      <div className="text-center text-muted p-2">
        <i>Status indisponível</i>
      </div>
    )
  }

  const automationStatus = getAutomationStatus(operador)

  const linha = (chave, partStatus, rotulo) => {
    const { isRunning, text } = partStatus
    const isError = String(text).toLowerCase().includes('erro')
    const icon = isError
      ? 'bi-exclamation-triangle-fill text-danger'
      : isRunning
        ? 'bi-check-circle-fill text-success'
        : 'bi-x-circle-fill text-muted'
    return (
      <div className="info-item" key={chave}>
        <span className={`info-label${rotulo ? '' : ' text-capitalize'}`}>
          {rotulo || chave}
        </span>
        <span className="info-value">
          <i className={`bi ${icon} me-1`} />{text}
        </span>
      </div>
    )
  }

  if (operador.tipo_cadastro === 'Ambos') {
    return (
      <>
        {linha('monitor', automationStatus.monitor)}
        {linha('totem', automationStatus.totem)}
      </>
    )
  }

  const partKey = operador.tipo_cadastro === 'Monitor de Senhas' ? 'monitor' : 'totem'
  return linha(partKey, automationStatus[partKey], 'Status')
}

export default function OperadorCard({
  operador, onComando, onEditar, onExcluir, podeAdministrar = false,
}) {
  const [detalheAberto, setDetalheAberto] = useState(false)
  const [senhaVisivel, setSenhaVisivel] = useState(false)

  // Menu de opções (três pontos) — estado do React + portal, para não ser
  // recortado pelo overflow do card. Comportamento preservado do original.
  const [menuAberto, setMenuAberto] = useState(false)
  const [posMenu, setPosMenu] = useState({ top: 0, left: 0 })
  const menuBotaoRef = useRef(null)
  const menuPainelRef = useRef(null)

  const alternarMenu = () => {
    if (!menuAberto && menuBotaoRef.current) {
      const r = menuBotaoRef.current.getBoundingClientRect()
      const largura = 200
      setPosMenu({
        top: Math.round(r.bottom + 6),
        left: Math.round(Math.min(r.right - largura, window.innerWidth - largura - 8)),
      })
    }
    setMenuAberto((v) => !v)
  }

  useEffect(() => {
    if (!menuAberto) return undefined
    const onClick = (e) => {
      const foraBotao = menuBotaoRef.current && !menuBotaoRef.current.contains(e.target)
      const foraPainel = !menuPainelRef.current || !menuPainelRef.current.contains(e.target)
      if (foraBotao && foraPainel) setMenuAberto(false)
    }
    const onEsc = (e) => { if (e.key === 'Escape') setMenuAberto(false) }
    const fechar = () => setMenuAberto(false)
    document.addEventListener('click', onClick)
    document.addEventListener('keydown', onEsc)
    window.addEventListener('resize', fechar)
    window.addEventListener('scroll', fechar, true)
    return () => {
      document.removeEventListener('click', onClick)
      document.removeEventListener('keydown', onEsc)
      window.removeEventListener('resize', fechar)
      window.removeEventListener('scroll', fechar, true)
    }
  }, [menuAberto])

  const isOnline = operador.online
  const tipo = TIPOS[operador.tipo_cadastro] || { cardClass: '', icones: [] }
  const automationStatus = getAutomationStatus(operador)
  const isAnyRunning = automationStatus.monitor.isRunning || automationStatus.totem.isRunning
  const nivel = operador.nivel_saude
  const temAlerta = isOnline && nivel && nivel !== 'Normal'

  const statusBadge = isOnline ? (
    <span className="badge bg-success-soft text-success">
      <i className="bi bi-check-circle-fill" /> Online
    </span>
  ) : (
    <span className="badge bg-danger-soft text-danger">
      <i className="bi bi-x-circle-fill" /> Offline
    </span>
  )

  const statusGeralBadge = isOnline
    ? isAnyRunning
      ? <span className="badge bg-info-soft text-info">Iniciado</span>
      : <span className="badge bg-warning-soft text-warning">Parado</span>
    : null

  const semPropagar = (fn) => (e) => { e.stopPropagation(); fn && fn(e) }
  const abrirDetalhe = () => setDetalheAberto(true)
  const onCardKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      abrirDetalhe()
    }
  }

  return (
    <>
    <div
      className={`operador-card-repaginado ${tipo.cardClass}`}
      role="button"
      tabIndex={0}
      aria-haspopup="dialog"
      onClick={abrirDetalhe}
      onKeyDown={onCardKey}
      title="Ver detalhes do operador"
    >
      <div className="card-body">
        <div className="operador-header">
          <div className="operador-nome">{operador.nome}</div>
          <div className="operador-status-badge">
            {temAlerta && (
              <i
                className={`bi bi-exclamation-triangle-fill me-2 ${nivel === 'Crítico' ? 'text-danger' : 'text-warning'}`}
                title={`Saúde: ${nivel}`}
              />
            )}
            {statusBadge}
          </div>
        </div>

        <div className="operador-info">
          <div className="info-item">
            <span className="info-label">Hostname</span>
            <span className="info-value font-monospace">{operador.hostname || 'N/A'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Tipo</span>
            <span className="info-value">
              {tipo.icones.map((ic, i) => (
                <span key={ic.src}>
                  {i > 0 && <>&nbsp; </>}
                  <img src={ic.src} className="type-icon-img" title={ic.title} alt={ic.title} />
                </span>
              ))}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">Usuário Tasy</span>
            <span className="info-value font-monospace">{operador.username || 'N/A'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Senha</span>
            <div
              className="d-flex align-items-center justify-content-end"
              style={{ minWidth: 0, flex: 1, marginLeft: 10 }}
            >
              <span
                className={`info-value font-monospace text-truncate${senhaVisivel ? ' text-primary' : ''}`}
                style={{ marginRight: 8 }}
              >
                {senhaVisivel ? (operador.password || '') : '********'}
              </span>
              <button
                className="btn btn-link btn-sm text-muted p-0 border-0 text-decoration-none"
                type="button"
                onClick={semPropagar(() => setSenhaVisivel((v) => !v))}
                title="Revelar/Ocultar senha"
                style={{ lineHeight: 1 }}
              >
                <i
                  className={senhaVisivel ? 'bi bi-eye-fill text-primary' : 'bi bi-eye-slash-fill'}
                />
              </button>
            </div>
          </div>
          <div className="info-item">
            <span className="info-label">Endereço IP</span>
            <span className="info-value font-monospace">{operador.ip || 'N/A'}</span>
          </div>
        </div>

        <div className="automation-status">
          <h6 className="automation-status-title">
            Status da Automação {statusGeralBadge}
          </h6>
          <div><StatusDetalhes operador={operador} /></div>
        </div>

        <button
          type="button"
          className="op-ver-detalhes"
          onClick={semPropagar(abrirDetalhe)}
        >
          <i className="bi bi-arrows-angle-expand me-1" />Ver detalhes
        </button>

        <div className="action-section mt-auto" onClick={(e) => e.stopPropagation()}>
          <div className="btn-group w-100 action-buttons" role="group">
            <button
              className={`btn btn-action-control btn-iniciar${isAnyRunning ? ' no-hover-effect' : ''}`}
              onClick={() => onComando(operador, 'iniciar')}
              title="Iniciar" disabled={!isOnline}
            >
              <i className="bi bi-play-fill" />
            </button>
            <button
              className={`btn btn-action-control btn-parar${!isAnyRunning ? ' no-hover-effect' : ''}`}
              onClick={() => onComando(operador, 'parar')}
              title="Parar" disabled={!isOnline}
            >
              <i className="bi bi-stop-fill" />
            </button>
            <button
              className="btn btn-action-control btn-reiniciar"
              onClick={() => onComando(operador, 'reiniciar')}
              title="Reiniciar" disabled={!isOnline}
            >
              <i className="bi bi-arrow-clockwise" />
            </button>
            {podeAdministrar && (
              <button
                ref={menuBotaoRef}
                type="button"
                className="btn btn-action-control btn-config"
                onClick={alternarMenu}
                aria-expanded={menuAberto}
                aria-haspopup="menu"
                title="Mais opções"
              >
                <i className="bi bi-three-dots-vertical" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>

      {menuAberto && podeAdministrar && createPortal(
        <div className="card-menu-painel" role="menu" ref={menuPainelRef}
             style={{ top: posMenu.top, left: posMenu.left }}>
          <button type="button" className="card-menu-item" role="menuitem"
                  onClick={() => { setMenuAberto(false); onEditar(operador.id) }}>
            <i className="bi bi-pencil-fill" />
            <span>Editar Operador</span>
          </button>
          <button type="button" className="card-menu-item perigo" role="menuitem"
                  onClick={() => { setMenuAberto(false); onExcluir(operador) }}>
            <i className="bi bi-trash-fill" />
            <span>Excluir Operador</span>
          </button>
        </div>,
        document.body
      )}

      <ModalDetalheOperador
        operador={operador}
        aberto={detalheAberto}
        onFechar={() => setDetalheAberto(false)}
      />
    </>
  )
}
