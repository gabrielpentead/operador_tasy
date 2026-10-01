import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { LOGIN_MAX, SENHA_MAX } from '../config/constants'
import ModalEsqueciSenha from '../components/modals/ModalEsqueciSenha'
import { authApi } from '../services/auth'

/**
 * Tela de login.
 *
 * Composição pedida: vídeo institucional em tela cheia, overlay escuro por
 * cima para garantir leitura, e um container centralizado com a identidade do
 * sistema. As cores, raios de borda e sombras vêm das variáveis do style.css
 * já usadas no restante do painel — nada de paleta nova.
 *
 * O vídeo é decorativo: `muted`, `playsInline` e `aria-hidden` para não
 * atrapalhar leitores de tela nem disparar bloqueio de autoplay.
 */
export default function Login() {
  const { entrar } = useAuth()
  const [login, setLogin] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [videoOk, setVideoOk] = useState(true)
  const [modalSenha, setModalSenha] = useState(false)
  const loginRef = useRef(null)

  useEffect(() => { loginRef.current?.focus() }, [])

  const submeter = async (e) => {
    e.preventDefault()
    if (enviando) return

    if (!login.trim() || !senha) {
      setErro('Informe usuário e senha')
      return
    }

    setEnviando(true)
    setErro('')
    const r = await entrar(login.trim(), senha)
    if (!r.ok) {
      setErro(r.erro)
      setSenha('')
      setEnviando(false)
    }
    // Sucesso não desliga o "enviando": o App troca a tela na sequência.
  }

  return (
    <div className="login-tela">
      {videoOk && (
        <video
          className="login-video"
          src="/static/video/institucional.mp4"
          autoPlay
          loop
          muted
          playsInline
          aria-hidden="true"
          onError={() => setVideoOk(false)}
        />
      )}
      <div className="login-overlay" />

      <div className="login-container">
        <div className="login-marca">
          <img src="/static/img/logo.png" alt="Hospital São Vicente" className="login-logo" />
          <h1 className="login-titulo">Central de Operadores</h1>
          <p className="login-subtitulo">Hospital São Vicente</p>
        </div>

        <form onSubmit={submeter} noValidate>
          <div className="mb-3">
            <label htmlFor="login-usuario" className="form-label login-label">Usuário</label>
            <div className="input-group">
              <span className="input-group-text"><i className="bi bi-person" /></span>
              <input
                id="login-usuario"
                ref={loginRef}
                type="text"
                className="form-control"
                value={login}
                onChange={(e) => { setLogin(e.target.value.slice(0, LOGIN_MAX)); setErro('') }}
                maxLength={LOGIN_MAX}
                autoComplete="username"
                disabled={enviando}
              />
            </div>
          </div>

          <div className="mb-3">
            <label htmlFor="login-senha" className="form-label login-label">Senha</label>
            <div className="input-group">
              <span className="input-group-text"><i className="bi bi-lock" /></span>
              <input
                id="login-senha"
                type="password"
                className="form-control"
                value={senha}
                onChange={(e) => { setSenha(e.target.value.slice(0, SENHA_MAX)); setErro('') }}
                maxLength={SENHA_MAX}
                autoComplete="current-password"
                disabled={enviando}
              />
            </div>
          </div>

          {erro && (
            <div className="login-erro" role="alert">
              <i className="bi bi-exclamation-circle-fill me-2" />
              {erro}
            </div>
          )}

          <button type="submit" className="btn btn-primary w-100 login-botao" disabled={enviando}>
            {enviando ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                Entrando…
              </>
            ) : (
              <>
                <i className="bi bi-box-arrow-in-right me-2" />
                Entrar
              </>
            )}
          </button>
        </form>

        <button
          type="button"
          className="login-esqueci"
          onClick={() => setModalSenha(true)}
          disabled={enviando}
        >
          Esqueci minha senha
        </button>

        <p className="login-rodape">NTI — Núcleo de Tecnologia da Informação</p>
      </div>

      <ModalEsqueciSenha
        aberto={modalSenha}
        onFechar={() => setModalSenha(false)}
        onEnviar={async (email) => {
          const r = await authApi.esqueciSenha(email)
          return (r.ok && r.success) ? {} : { erro: r.error || 'Não foi possível enviar' }
        }}
      />
    </div>
  )
}
