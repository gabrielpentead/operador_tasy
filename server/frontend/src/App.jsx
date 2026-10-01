import { useState } from 'react'
import { ToastProvider } from './context/ToastContext'
import { NotificacoesProvider } from './context/NotificacoesContext'
import { OperadoresProvider } from './context/OperadoresContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { AcessibilidadeProvider, useAcessibilidade } from './context/AcessibilidadeContext'
import VLibrasWidget from './components/acessibilidade/VLibrasWidget'

import Header from './components/layout/Header'
import ConnectionStatus from './components/layout/ConnectionStatus'
import OfflineToasts from './components/notifications/OfflineToasts'
import Dashboard from './pages/Dashboard'
import Configuracoes from './pages/Configuracoes'
import Login from './pages/Login'
import RedefinirSenha from './pages/RedefinirSenha'

/** Lê o token do link de redefinição (?redefinir=...) enviado por e-mail. */
function tokenDaUrl() {
  try {
    return new URLSearchParams(window.location.search).get('redefinir') || null
  } catch {
    return null
  }
}

/**
 * Painel — só é montado depois que a sessão foi confirmada pelo servidor.
 *
 * Os providers de operadores só entram aqui dentro, de propósito: assim nenhum
 * dado do painel é buscado antes da autenticação, e o WebSocket não conecta
 * numa tela de login.
 */
function Painel() {
  const { isAdmin } = useAuth()
  const [pagina, setPagina] = useState('dashboard')

  // Configurações é aberta a todos, mas cada perfil vê só as seções permitidas
  // (a de Acessibilidade vale para qualquer um; as de admin são filtradas
  // dentro da própria página e protegidas no backend).
  const paginaEfetiva = pagina

  return (
    <NotificacoesProvider>
      <OperadoresProvider>
        <Header
          onIrParaConfiguracoes={() => setPagina('configuracoes')}
          onIrParaDashboard={() => setPagina('dashboard')}
        />
        {paginaEfetiva === 'configuracoes'
          ? <Configuracoes onVoltar={() => setPagina('dashboard')} isAdmin={isAdmin} />
          : <Dashboard />}
        <ConnectionStatus />
        <OfflineToasts />
      </OperadoresProvider>
    </NotificacoesProvider>
  )
}

/** Decide entre redefinição, login e painel conforme a URL e a sessão. */
function Raiz() {
  const { autenticado, carregando } = useAuth()
  const [token, setToken] = useState(tokenDaUrl)

  // O link de redefinição tem prioridade sobre tudo: quem chegou por ele veio
  // justamente porque não consegue entrar, e não faz sentido esbarrar antes na
  // tela de login. Vale também com sessão aberta — pode ser outra pessoa
  // usando a mesma máquina.
  if (token) {
    return (
      <RedefinirSenha
        token={token}
        onSair={() => {
          // Tira o token da barra de endereço: ele não precisa ficar no
          // histórico do navegador depois de usado.
          window.history.replaceState({}, '', window.location.pathname)
          setToken(null)
        }}
      />
    )
  }

  if (carregando) {
    return (
      <div className="auth-carregando">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Verificando sessão…</span>
        </div>
        <span>Verificando sessão…</span>
      </div>
    )
  }

  return autenticado ? <Painel /> : <Login />
}

/**
 * Ordem dos providers: ToastProvider por fora porque AuthProvider e os demais
 * podem notificar; AuthProvider antes do painel porque tudo lá depende da
 * sessão.
 */
/** Monta o widget do VLibras conforme a preferência de acessibilidade. */
function LibrasMontagem() {
  const { libras } = useAcessibilidade()
  return <VLibrasWidget ativo={libras} />
}

export default function App() {
  return (
    <AcessibilidadeProvider>
      <ToastProvider>
        <AuthProvider>
          <Raiz />
        </AuthProvider>
      </ToastProvider>
      {/* Fora dos demais providers: o VLibras vale em qualquer tela, inclusive login. */}
      <LibrasMontagem />
    </AcessibilidadeProvider>
  )
}
