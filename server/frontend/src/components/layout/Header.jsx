import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import NotifPanel from '../notifications/NotifPanel'
import { useNotificacoes } from '../../context/NotificacoesContext'
import { useAuth } from '../../context/AuthContext'

/**
 * Cabeçalho do painel.
 *
 * Duas ações fixas — notificações e o menu (☰) — e, dentro do menu, tudo que
 * antes disputava espaço na barra: identificação de quem está logado, acesso às
 * configurações e sair. Assim o header não cresce quando surgirem novas opções,
 * e continua legível no celular.
 *
 * Os painéis flutuantes são renderizados por PORTAL no body: a .navbar tem
 * `overflow: hidden` no style.css e recortava qualquer camada posicionada
 * dentro dela — mesma razão pela qual o painel de notificações já vivia fora do
 * header no HTML original.
 */
export default function Header({ onIrParaConfiguracoes, onIrParaDashboard }) {
  const [painelAberto, setPainelAberto] = useState(false)
  const [menuAberto, setMenuAberto] = useState(false)
  const [posMenu, setPosMenu] = useState({ top: 0, right: 0 })

  const { naoLidas } = useNotificacoes()
  const { usuario, isAdmin, sair } = useAuth()

  const sinoRef = useRef(null)
  const painelRef = useRef(null)
  const menuBotaoRef = useRef(null)
  const menuPainelRef = useRef(null)

  const iniciais = (usuario?.nome || '?')
    .trim().split(/\s+/).filter(Boolean)
    .map((parte, i, todas) => (i === 0 || i === todas.length - 1 ? parte[0] : ''))
    .join('').slice(0, 2).toUpperCase()

  // O painel é fixed no body, então precisa das coordenadas de viewport do botão.
  const alternarMenu = () => {
    if (!menuAberto && menuBotaoRef.current) {
      const r = menuBotaoRef.current.getBoundingClientRect()
      setPosMenu({
        top: Math.round(r.bottom + 10),
        right: Math.max(8, Math.round(window.innerWidth - r.right)),
      })
    }
    setMenuAberto((v) => !v)
  }

  useEffect(() => {
    const onClick = (e) => {
      if (
        painelRef.current && sinoRef.current &&
        !painelRef.current.contains(e.target) &&
        !sinoRef.current.contains(e.target)
      ) {
        setPainelAberto(false)
      }
      const foraDoBotao = menuBotaoRef.current && !menuBotaoRef.current.contains(e.target)
      const foraDoPainel = !menuPainelRef.current || !menuPainelRef.current.contains(e.target)
      if (foraDoBotao && foraDoPainel) setMenuAberto(false)
    }
    const onEsc = (e) => {
      if (e.key === 'Escape') { setMenuAberto(false); setPainelAberto(false) }
    }
    // Reposiciona ao redimensionar: coordenada fixa fica errada se a janela muda
    const onResize = () => setMenuAberto(false)

    document.addEventListener('click', onClick)
    document.addEventListener('keydown', onEsc)
    window.addEventListener('resize', onResize)
    return () => {
      document.removeEventListener('click', onClick)
      document.removeEventListener('keydown', onEsc)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  const irPara = (acao) => { setMenuAberto(false); acao?.() }

  return (
    <>
      <header className="navbar navbar-dark">
        <div className="container header-conteudo">
          <button type="button" className="navbar-brand header-marca" onClick={onIrParaDashboard}>
            <img src="/static/img/logo.png" alt="Logo HSV" className="logo-header" />
            <span className="brand-text">Central de Operadores - HSV</span>
          </button>

          <div className="header-acoes">
            <button
              ref={sinoRef}
              type="button"
              className={`notif-bell${naoLidas > 0 ? ' notif-bell-has-unread' : ''}`}
              onClick={() => setPainelAberto((v) => !v)}
              aria-label="Notificações"
              title="Notificações"
            >
              <i className="bi bi-bell-fill" />
              <span className={`notif-badge${naoLidas === 0 ? ' d-none' : ''}`}>
                {naoLidas > 99 ? '99+' : naoLidas}
              </span>
            </button>

            <button
              ref={menuBotaoRef}
              type="button"
              className={`header-menu-botao${menuAberto ? ' aberto' : ''}`}
              onClick={alternarMenu}
              aria-expanded={menuAberto}
              aria-haspopup="menu"
              aria-label="Menu"
              title="Menu"
            >
              <i className="bi bi-list" />
            </button>
          </div>
        </div>
      </header>

      <NotifPanel ref={painelRef} aberto={painelAberto} />

      {menuAberto && createPortal(
        <div
          className="header-menu-painel"
          role="menu"
          ref={menuPainelRef}
          style={{ top: posMenu.top, right: posMenu.right }}
        >
          <div className="header-menu-conta">
            <span className="header-menu-avatar">{iniciais}</span>
            <div className="header-menu-identidade">
              <span className="header-menu-nome">{usuario?.nome}</span>
              <span className="header-menu-login">
                {usuario?.login}
                <i
                  className={`bi bi-${isAdmin ? 'shield-lock-fill' : 'person-fill'} ms-2`}
                  title={isAdmin ? 'Administrador' : 'Operador'}
                />
              </span>
            </div>
          </div>

          <div className="header-menu-separador" />

          <button type="button" className="header-menu-item" role="menuitem"
                  onClick={() => irPara(onIrParaDashboard)}>
            <i className="bi bi-speedometer2" />
            <span>Painel</span>
          </button>

          {/* Configurações é aberta a todos: o operador vê só Acessibilidade;
              as seções de admin são filtradas dentro da página. */}
          <button type="button" className="header-menu-item" role="menuitem"
                  onClick={() => irPara(onIrParaConfiguracoes)}>
            <i className="bi bi-gear" />
            <span>Configurações</span>
          </button>

          <div className="header-menu-separador" />

          <button type="button" className="header-menu-item perigo" role="menuitem"
                  onClick={() => irPara(sair)}>
            <i className="bi bi-box-arrow-right" />
            <span>Sair</span>
          </button>
        </div>,
        document.body
      )}
    </>
  )
}
