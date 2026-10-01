import { useState, useEffect, useRef } from 'react'
import { SENHA_MIN, SENHA_MAX } from '../config/constants'
import { authApi } from '../services/auth'

/**
 * Tela de "definir nova senha", aberta pelo link recebido por e-mail.
 *
 * Reaproveita a mesma moldura visual do login (vídeo, overlay, container) para
 * a pessoa perceber que continua no sistema certo — nada de página solta com
 * outro visual, que é justamente a aparência que golpes de phishing têm.
 *
 * Estados possíveis:
 *   'verificando' → consultando o servidor se o link ainda vale
 *   'invalido'    → link expirado, já usado ou inexistente
 *   'formulario'  → link válido, esperando a nova senha
 *   'pronto'      → senha trocada, oferece voltar ao login
 */
export default function RedefinirSenha({ token, onSair }) {
  const [estado, setEstado] = useState('verificando')
  const [dono, setDono] = useState(null)
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [videoOk, setVideoOk] = useState(true)
  const senhaRef = useRef(null)

  // Valida o link antes de mostrar o formulário: evita a pessoa digitar a
  // senha duas vezes para só então descobrir que o link expirou.
  useEffect(() => {
    let vivo = true
    ;(async () => {
      const r = await authApi.validarToken(token)
      if (!vivo) return
      if (r.ok && r.valido) {
        setDono({ nome: r.nome, login: r.login })
        setEstado('formulario')
        setTimeout(() => senhaRef.current?.focus(), 80)
      } else {
        setErro(r.error || 'Este link não é mais válido.')
        setEstado('invalido')
      }
    })()
    return () => { vivo = false }
  }, [token])

  const submeter = async (e) => {
    e.preventDefault()
    if (enviando) return

    if (senha.length < SENHA_MIN) {
      setErro(`A senha precisa ter ao menos ${SENHA_MIN} caracteres`)
      return
    }
    if (senha !== confirmacao) {
      setErro('As senhas não conferem')
      return
    }

    setEnviando(true)
    setErro('')
    const r = await authApi.redefinirComToken(token, senha)
    if (r.ok && r.success) {
      setEstado('pronto')
    } else {
      setErro(r.error || 'Não foi possível redefinir a senha')
      setEnviando(false)
    }
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

        {estado === 'verificando' && (
          <div className="text-center py-4">
            <span className="spinner-border text-light" role="status" aria-hidden="true" />
            <p className="login-subtitulo mt-3 mb-0">Verificando o link…</p>
          </div>
        )}

        {estado === 'invalido' && (
          <div className="text-center py-2">
            <i className="bi bi-x-circle-fill" style={{ fontSize: '2.5rem', color: '#e57373' }} />
            <p className="login-label mt-3 mb-1">Link inválido</p>
            <p className="login-subtitulo mb-0">{erro}</p>
            <p className="login-subtitulo small mt-2 mb-0">
              Peça um novo link em “Esqueci minha senha”.
            </p>
            <button type="button" className="btn btn-primary w-100 login-botao mt-4" onClick={onSair}>
              <i className="bi bi-arrow-left me-2" />
              Voltar ao login
            </button>
          </div>
        )}

        {estado === 'pronto' && (
          <div className="text-center py-2">
            <i className="bi bi-check-circle-fill" style={{ fontSize: '2.5rem', color: '#81c784' }} />
            <p className="login-label mt-3 mb-1">Senha alterada</p>
            <p className="login-subtitulo mb-0">Você já pode entrar com a nova senha.</p>
            <button type="button" className="btn btn-primary w-100 login-botao mt-4" onClick={onSair}>
              <i className="bi bi-box-arrow-in-right me-2" />
              Ir para o login
            </button>
          </div>
        )}

        {estado === 'formulario' && (
          <form onSubmit={submeter} noValidate>
            <p className="login-subtitulo mb-3">
              Olá, <strong>{dono?.nome}</strong>. Escolha a nova senha da conta{' '}
              <strong>{dono?.login}</strong>.
            </p>

            <div className="mb-3">
              <label htmlFor="nova-senha" className="form-label login-label">Nova senha</label>
              <div className="input-group">
                <span className="input-group-text"><i className="bi bi-lock" /></span>
                <input
                  id="nova-senha"
                  ref={senhaRef}
                  type="password"
                  className="form-control"
                  value={senha}
                  onChange={(e) => { setSenha(e.target.value.slice(0, SENHA_MAX)); setErro('') }}
                  maxLength={SENHA_MAX}
                  autoComplete="new-password"
                  disabled={enviando}
                />
              </div>
              <div className="login-subtitulo small mt-1">
                De {SENHA_MIN} a {SENHA_MAX} caracteres.
              </div>
            </div>

            <div className="mb-3">
              <label htmlFor="confirma-senha" className="form-label login-label">Repita a senha</label>
              <div className="input-group">
                <span className="input-group-text"><i className="bi bi-lock-fill" /></span>
                <input
                  id="confirma-senha"
                  type="password"
                  className="form-control"
                  value={confirmacao}
                  onChange={(e) => { setConfirmacao(e.target.value.slice(0, SENHA_MAX)); setErro('') }}
                  maxLength={SENHA_MAX}
                  autoComplete="new-password"
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
                  Salvando…
                </>
              ) : (
                <>
                  <i className="bi bi-check-lg me-2" />
                  Salvar nova senha
                </>
              )}
            </button>

            <button type="button" className="login-esqueci" onClick={onSair} disabled={enviando}>
              Cancelar e voltar ao login
            </button>
          </form>
        )}

        <p className="login-rodape">NTI — Núcleo de Tecnologia da Informação</p>
      </div>
    </div>
  )
}
