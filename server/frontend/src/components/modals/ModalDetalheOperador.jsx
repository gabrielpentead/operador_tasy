import { useState, useEffect, useCallback } from 'react'
import Modal from './Modal'
import { getAutomationStatus } from '../../utils/status'
import { corPorLimiar } from '../../utils/health'
import { formatarData } from '../../utils/format'
import { listarEventosOperador } from '../../services/api'
import { socket, EVENTOS } from '../../services/socket'

/**
 * Visão detalhada de um operador — abre como painel sobre o dashboard (modal),
 * não como nova página. Reúne saúde, automação, voz/idioma, conexão e versão em
 * seções, com espaço de sobra para novas informações (reinícios, erros, etc.).
 *
 * Só apresenta dados que já chegam do servidor; campos ausentes aparecem como
 * "não informado" em vez de sumir de forma inconsistente.
 */

function nomeCurtoVoz(voz) {
  if (!voz) return null
  const m = voz.match(/Microsoft\s+([A-Za-zÀ-ÿ]+)/)
  return m ? m[1] : voz
}

const IDIOMAS = {
  'pt-BR': 'Português (Brasil)',
  'pt-PT': 'Português (Portugal)',
  'en-US': 'Inglês (EUA)',
  'es-ES': 'Espanhol (Espanha)',
}
function nomeIdioma(idioma) {
  if (!idioma) return null
  return IDIOMAS[idioma] ? `${IDIOMAS[idioma]} — ${idioma}` : idioma
}

function LinhaInfo({ rotulo, children, mono }) {
  return (
    <div className="info-item">
      <span className="info-label">{rotulo}</span>
      <span className={`info-value${mono ? ' font-monospace' : ''}`}>{children}</span>
    </div>
  )
}

/**
 * Bloco rótulo-em-cima/valor-embaixo, usado no grid de Conexão. A lista
 * label-à-esquerda/valor-à-direita (LinhaInfo) fica esticada demais numa
 * seção larga: rótulo curto e valor curto grudados nas duas pontas, com um
 * vão vazio enorme no meio. Em blocos lado a lado isso não acontece.
 */
function BlocoInfo({ rotulo, children, mono }) {
  return (
    <div className="op-conexao-bloco">
      <span className="op-conexao-rotulo">{rotulo}</span>
      <span className={`op-conexao-valor${mono ? ' font-monospace' : ''}`}>{children}</span>
    </div>
  )
}

function BlocoSenha({ senha }) {
  const [visivel, setVisivel] = useState(false)
  return (
    <div className="op-conexao-bloco">
      <span className="op-conexao-rotulo">Senha Tasy</span>
      <span className="op-conexao-valor font-monospace op-conexao-valor-senha">
        <span className={`text-truncate${visivel ? ' text-primary' : ''}`}>
          {visivel ? (senha || 'N/A') : '••••••••'}
        </span>
        <button
          type="button"
          className="btn btn-link btn-sm text-muted p-0 border-0 text-decoration-none op-olho"
          onClick={() => setVisivel((v) => !v)}
          title={visivel ? 'Ocultar senha' : 'Revelar senha'}
          aria-label={visivel ? 'Ocultar senha' : 'Revelar senha'}
        >
          <i className={visivel ? 'bi bi-eye-fill text-primary' : 'bi bi-eye-slash-fill'} />
        </button>
      </span>
    </div>
  )
}

function StatusAutomacao({ operador }) {
  if (!operador.online || !operador.status) {
    return <p className="op-secao-vazia">Status indisponível (operador offline).</p>
  }
  const auto = getAutomationStatus(operador)
  const linha = (rotulo, part) => {
    const isError = String(part.text).toLowerCase().includes('erro')
    const icon = isError
      ? 'bi-exclamation-triangle-fill text-danger'
      : part.isRunning ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-muted'
    return (
      <div className="info-item" key={rotulo}>
        <span className="info-label">{rotulo}</span>
        <span className="info-value"><i className={`bi ${icon} me-1`} />{part.text}</span>
      </div>
    )
  }
  if (operador.tipo_cadastro === 'Ambos') {
    return <>{linha('Monitor', auto.monitor)}{linha('Totem', auto.totem)}</>
  }
  const part = operador.tipo_cadastro === 'Monitor de Senhas' ? auto.monitor : auto.totem
  return linha('Status', part)
}

// Mesma linguagem visual do card "Servidor" do dashboard (ServerHealthCard):
// ícone colorido + valor + barra fina. CPU/RAM/Disco têm escala 0-100%, então
// ganham barra; Temperatura não (escala é em °C), por isso mostra um rótulo
// de status no lugar — igual ao card do servidor.
const METRICA_META = {
  cpu:         { label: 'CPU',   icon: 'bi-cpu',              cor: '#3b82f6', limiares: [[70, '#f59e0b'], [90, '#ef4444']] },
  ram:         { label: 'RAM',   icon: 'bi-memory',           cor: '#8b5cf6', limiares: [[70, '#f59e0b'], [90, '#ef4444']] },
  disco:       { label: 'Disco', icon: 'bi-device-hdd',       cor: '#f59e0b', limiares: [[70, '#ef4444']] },
  temperatura: { label: 'Temp.', icon: 'bi-thermometer-half', cor: '#ef4444', limiares: [[75, '#f59e0b'], [85, '#ef4444']] },
}

function rotuloTemperatura(cor) {
  if (cor === '#ef4444') return 'Alta'
  if (cor === '#f59e0b') return 'Elevada'
  return 'Normal'
}

function Saude({ saude, nivel, motivos }) {
  const nivelBadge = nivel && nivel !== 'Normal' ? (
    <span className={`badge ${nivel === 'Crítico' ? 'bg-danger-soft text-danger' : 'bg-warning-soft text-warning'}`}>{nivel}</span>
  ) : <span className="badge bg-success-soft text-success">Normal</span>

  const metricas = saude ? [
    { valor: saude.cpu_pct, campo: 'cpu' },
    { valor: saude.ram_pct, campo: 'ram' },
    { valor: saude.disco_pct, campo: 'disco' },
    { valor: saude.temperatura, campo: 'temperatura' },
  ].filter((m) => m.valor !== null && m.valor !== undefined) : []

  return (
    <>
      <div className="op-secao-head">
        <span className="op-secao-titulo"><i className="bi bi-heart-pulse me-1" />Saúde do painel</span>
        {saude && nivelBadge}
      </div>
      {metricas.length ? (
        <div className="op-saude-grid">
          {metricas.map((m) => {
            const meta = METRICA_META[m.campo]
            const cor = corPorLimiar(m.valor, meta.cor, meta.limiares)
            const ehTemperatura = m.campo === 'temperatura'
            return (
              <div className="op-saude-metrica" key={m.campo}>
                <div className="op-saude-metrica-topo">
                  <span className="op-saude-icon" style={{ color: cor, background: `${cor}1f` }}>
                    <i className={`bi ${meta.icon}`} />
                  </span>
                  <div className="op-saude-metrica-texto">
                    <span className="op-saude-label">{meta.label}</span>
                    <span className="op-saude-valor" style={{ color: cor }}>
                      {Math.round(m.valor)}{ehTemperatura ? '°C' : '%'}
                    </span>
                  </div>
                </div>
                {ehTemperatura ? (
                  <span className="op-saude-status" style={{ color: cor }}>{rotuloTemperatura(cor)}</span>
                ) : (
                  <div className="op-saude-bar-track">
                    <div className="op-saude-bar-fill" style={{ width: `${Math.min(m.valor, 100)}%`, background: cor }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : <p className="op-secao-vazia">Sem dados de saúde no momento.</p>}
      {motivos && motivos.length > 0 && (
        <ul className="op-saude-motivos">
          {motivos.map((mot, i) => <li key={i}><i className="bi bi-exclamation-circle me-1" />{mot}</li>)}
        </ul>
      )}
    </>
  )
}

function duracaoLegivel(s) {
  if (s === null || s === undefined) return '—'
  if (s < 60) return `${s}s`
  const min = Math.floor(s / 60)
  const seg = s % 60
  return seg ? `${min}min ${seg}s` : `${min}min`
}

// Um reinício isolado, no formato de sempre. Reusado solto e dentro da rajada.
function LinhaReinicio({ ev }) {
  const d = ev.dados || {}
  const nivel = ev.nivel || d.resultado
  // 'pendente': o servidor ainda não confirmou se a automação subiu —
  // não mostra Sucesso/Falha nem tempo enquanto isso.
  const pendente = nivel === 'pendente' || !nivel
  const sucesso = nivel === 'sucesso'
  return (
    <li className="op-evento">
      <div className="op-evento-topo">
        <span className="op-evento-titulo">
          <i className={`bi bi-arrow-repeat me-1${pendente ? ' op-evento-girando' : ''}`} />
          {ev.titulo || 'Reinicialização'}
        </span>
        <span className="op-evento-quando">{formatarData(ev.ocorrido_em)}</span>
      </div>
      <div className="op-evento-corpo">
        {d.duracao_s !== undefined && (
          <span className="op-evento-tag"><i className="bi bi-stopwatch me-1" />{duracaoLegivel(d.duracao_s)}</span>
        )}
        {pendente ? (
          <span className="badge bg-info-soft text-info">Iniciado…</span>
        ) : (
          <span className={`badge ${sucesso ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'}`}>
            {sucesso ? 'Sucesso' : 'Falha'}
          </span>
        )}
      </div>
    </li>
  )
}

const RAJADA_MIN = 3                 // a partir de 3 reinícios próximos vira "rajada"
const RAJADA_GAP_MS = 10 * 60 * 1000 // reinícios a até 10 min um do outro = mesma rajada

function _ts(s) {
  const d = new Date(String(s).replace(' ', 'T'))
  return isNaN(d.getTime()) ? null : d.getTime()
}
function _hora(s) {
  const t = _ts(s)
  return t === null ? '—' : new Date(t).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

// Agrupa reinícios consecutivos e próximos no tempo (lista vem do mais novo p/ o
// mais antigo). Uma tempestade de reinícios vira um grupo só, em vez de dezenas
// de linhas quase iguais.
function agruparReinicios(lista) {
  const grupos = []
  let atual = null
  for (const ev of lista) {
    const t = _ts(ev.ocorrido_em)
    if (atual && t !== null && atual.ultimoTs !== null &&
        (atual.ultimoTs - t) <= RAJADA_GAP_MS) {
      atual.eventos.push(ev)
      atual.ultimoTs = t
    } else {
      atual = { eventos: [ev], ultimoTs: t }
      grupos.push(atual)
    }
  }
  return grupos
}

function Reinicios({ lista }) {
  const [abertos, setAbertos] = useState({})
  if (!lista || lista.length === 0) {
    return <p className="op-secao-vazia">Nenhuma reinicialização registrada.</p>
  }
  const grupos = agruparReinicios(lista)
  return (
    <ul className="op-eventos">
      {grupos.map((g, i) => {
        // Grupo pequeno: mostra cada reinício como antes.
        if (g.eventos.length < RAJADA_MIN) {
          return g.eventos.map((ev) => <LinhaReinicio key={ev.id} ev={ev} />)
        }
        // Rajada: um card resumido, expansível.
        const n = g.eventos.length
        const conta = (nome) => g.eventos.filter((e) => {
          const nv = e.nivel || (e.dados || {}).resultado
          if (nome === 'sucesso') return nv === 'sucesso'
          if (nome === 'pendente') return nv === 'pendente' || !nv
          return nv && nv !== 'sucesso' && nv !== 'pendente'   // falha
        }).length
        const falhas = conta('falha'), sucessos = conta('sucesso'), pendentes = conta('pendente')
        const novo = g.eventos[0], velho = g.eventos[n - 1]
        const aberto = !!abertos[i]
        return (
          <li className="op-evento" key={`rajada-${novo.id}`}>
            <div className="op-evento-topo">
              <span className="op-evento-titulo">
                <i className="bi bi-arrow-repeat me-1" />Tempestade de reinícios
              </span>
              <span className="op-evento-quando">{_hora(velho.ocorrido_em)}–{_hora(novo.ocorrido_em)}</span>
            </div>
            <div className="op-evento-corpo">
              <span className="op-evento-tag">{n} reinícios</span>
              {falhas > 0 && <span className="badge bg-danger-soft text-danger">{falhas} falha{falhas > 1 ? 's' : ''}</span>}
              {sucessos > 0 && <span className="badge bg-success-soft text-success">{sucessos} sucesso{sucessos > 1 ? 's' : ''}</span>}
              {pendentes > 0 && <span className="badge bg-info-soft text-info">{pendentes} em andamento</span>}
              <button type="button" className="op-evento-link"
                      onClick={() => setAbertos((a) => ({ ...a, [i]: !a[i] }))}>
                {aberto ? 'ocultar' : 'ver todos'}
              </button>
            </div>
            {aberto && (
              <ul className="op-eventos" style={{ marginTop: 8 }}>
                {g.eventos.map((ev) => <LinhaReinicio key={ev.id} ev={ev} />)}
              </ul>
            )}
          </li>
        )
      })}
    </ul>
  )
}

const NIVEL_ERRO = {
  critico: { cls: 'bg-danger-soft text-danger', rotulo: 'Crítico', icon: 'bi-exclamation-octagon-fill' },
  erro:    { cls: 'bg-danger-soft text-danger', rotulo: 'Erro', icon: 'bi-x-octagon-fill' },
  aviso:   { cls: 'bg-warning-soft text-warning', rotulo: 'Aviso', icon: 'bi-exclamation-triangle-fill' },
}

function Erros({ lista }) {
  const [aberto, setAberto] = useState(null)
  if (!lista || lista.length === 0) {
    return <p className="op-secao-vazia">Nenhuma ocorrência recente. 🎉</p>
  }
  return (
    <ul className="op-eventos">
      {lista.map((ev) => {
        const meta = NIVEL_ERRO[ev.nivel] || NIVEL_ERRO.erro
        const d = ev.dados || {}
        const ocorrencias = d.ocorrencias || 1
        const expandido = aberto === ev.id
        return (
          <li className="op-evento" key={ev.id}>
            <div className="op-evento-topo">
              <span className="op-evento-titulo">
                <i className={`bi ${meta.icon} me-1`} />{ev.titulo || 'Ocorrência'}
              </span>
              <span className="op-evento-quando">{formatarData(ev.ocorrido_em)}</span>
            </div>
            <div className="op-evento-corpo">
              <span className={`badge ${meta.cls}`}>{meta.rotulo}</span>
              {ocorrencias > 1 && <span className="op-evento-tag">{ocorrencias}× recentes</span>}
              {ev.detalhe && (
                <button type="button" className="op-evento-link"
                        onClick={() => setAberto(expandido ? null : ev.id)}>
                  {expandido ? 'ocultar' : 'ver detalhes'}
                </button>
              )}
            </div>
            {expandido && ev.detalhe && (
              <pre className="op-evento-detalhe">{ev.detalhe}</pre>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function ModalDetalheOperador({ operador, aberto, onFechar }) {
  const [eventos, setEventos] = useState({ reinicios: [], erros: [], resumo: {} })
  const [carregandoEventos, setCarregandoEventos] = useState(false)

  const operadorId = operador?.id

  const carregarEventos = useCallback(async () => {
    if (!operadorId) return
    setCarregandoEventos(true)
    try {
      const r = await listarEventosOperador(operadorId)
      if (r.success) {
        setEventos({ reinicios: r.reinicios || [], erros: r.erros || [], resumo: r.resumo || {} })
      }
    } catch { /* silencioso: a seção mostra o estado vazio */ }
    setCarregandoEventos(false)
  }, [operadorId])

  // Busca ao abrir; e atualiza ao vivo quando o servidor sinaliza eventos novos
  // deste operador enquanto o painel está aberto.
  useEffect(() => {
    if (!aberto || !operadorId) return undefined
    carregarEventos()
    const onNovos = (data) => { if (data && data.id === operadorId) carregarEventos() }
    socket.on(EVENTOS.EVENTOS_ATUALIZADOS, onNovos)
    return () => socket.off(EVENTOS.EVENTOS_ATUALIZADOS, onNovos)
  }, [aberto, operadorId, carregarEventos])

  if (!operador) return null

  const isOnline = operador.online
  const auto = getAutomationStatus(operador)
  const isAnyRunning = auto.monitor.isRunning || auto.totem.isRunning
  const nivel = operador.nivel_saude
  const vozCurta = nomeCurtoVoz(operador.voz)
  const idiomaLabel = nomeIdioma(operador.idioma)

  const statusBadge = isOnline
    ? <span className="badge bg-success-soft text-success"><i className="bi bi-check-circle-fill" /> Online</span>
    : <span className="badge bg-danger-soft text-danger"><i className="bi bi-x-circle-fill" /> Offline</span>
  const automacaoBadge = isOnline
    ? (isAnyRunning
        ? <span className="badge bg-info-soft text-info">Iniciado</span>
        : <span className="badge bg-warning-soft text-warning">Parado</span>)
    : null

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      titulo={operador.nome}
      icone="bi-display"
      tamanho="modal-lg modal-dialog-scrollable"
    >
      <div className="op-modal">
        {/* Faixa-resumo no topo */}
        <div className="op-modal-resumo">
          {statusBadge}
          {automacaoBadge}
          <span className="badge bg-light text-dark">{operador.tipo_cadastro || 'N/A'}</span>
          <span className={`badge ${operador.versao ? 'bg-secondary' : 'bg-light text-muted'}`}>
            <i className="bi bi-box-seam me-1" />{operador.versao ? `v${operador.versao}` : 'versão N/D'}
          </span>
          {isOnline && nivel && (
            <span className={`badge ${nivel === 'Crítico' ? 'bg-danger-soft text-danger'
              : nivel === 'Atenção' ? 'bg-warning-soft text-warning' : 'bg-success-soft text-success'}`}>
              <i className="bi bi-heart-pulse me-1" />{nivel}
            </span>
          )}
        </div>

        {/* Grid responsivo: cada seção é um cartão independente que flui
            sozinho (auto-fit) — em vez de duas colunas com altura calculada
            manualmente, que quebravam de forma estranha em modais estreitos. */}
        <div className="op-modal-grid">
          <section className="op-secao op-card"><Saude saude={operador.saude} nivel={nivel} motivos={operador.motivos} /></section>

          {/* Automação + Voz/idioma dividem um cartão: cada uma sozinha tem
              pouco conteúdo (uma linha, ou duas) e ficava com um cartão do
              tamanho do de Saúde só de vão vazio embaixo. */}
          <section className="op-secao op-card">
            <div className="op-secao-head">
              <span className="op-secao-titulo"><i className="bi bi-diagram-3 me-1" />Status da automação</span>
              {automacaoBadge}
            </div>
            <StatusAutomacao operador={operador} />

            <div className="op-secao-head op-secao-head-sub">
              <span className="op-secao-titulo"><i className="bi bi-mic me-1" />Voz e idioma</span>
            </div>
            {vozCurta || idiomaLabel ? (
              <>
                <LinhaInfo rotulo="Voz">{vozCurta || 'não informado'}</LinhaInfo>
                <LinhaInfo rotulo="Idioma">{idiomaLabel || 'não informado'}</LinhaInfo>
              </>
            ) : <p className="op-secao-vazia">Não informado por este operador.</p>}
          </section>

          <section className="op-secao op-card op-card-conexao">
            <div className="op-secao-head">
              <span className="op-secao-titulo"><i className="bi bi-hdd-network me-1" />Conexão</span>
            </div>
            <div className="op-conexao-grid">
              <BlocoInfo rotulo="Hostname" mono>{operador.hostname || 'N/A'}</BlocoInfo>
              <BlocoInfo rotulo={isOnline ? 'Endereço IP' : 'Último IP conhecido'} mono>
                {operador.ip || 'N/A'}
              </BlocoInfo>
              <BlocoInfo rotulo="Usuário Tasy" mono>{operador.username || 'N/A'}</BlocoInfo>
              <BlocoSenha senha={operador.password} />
            </div>
          </section>
        </div>

        {/* Reinícios e erros ocupam a largura toda, empilhados */}
        <div className="op-modal-full">
          <section className="op-secao op-card">
            <div className="op-secao-head">
              <span className="op-secao-titulo"><i className="bi bi-arrow-repeat me-1" />Reinicializações</span>
              {eventos.resumo.reinicios_24h > 0 && (
                <span className="badge bg-light text-dark">{eventos.resumo.reinicios_24h} nas últimas 24h</span>
              )}
            </div>
            {carregandoEventos ? <p className="op-secao-vazia">Carregando…</p>
              : <Reinicios lista={eventos.reinicios} />}
          </section>

          <section className="op-secao op-card">
            <div className="op-secao-head">
              <span className="op-secao-titulo"><i className="bi bi-exclamation-triangle me-1" />Erros e ocorrências</span>
              {eventos.resumo.erros_24h > 0 && (
                <span className="badge bg-warning-soft text-warning">{eventos.resumo.erros_24h} nas últimas 24h</span>
              )}
            </div>
            {carregandoEventos ? <p className="op-secao-vazia">Carregando…</p>
              : <Erros lista={eventos.erros} />}
          </section>
        </div>
      </div>
    </Modal>
  )
}
