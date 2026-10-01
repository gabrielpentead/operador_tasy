import { useServerHealth } from '../../hooks/useServerHealth'
import { corPorLimiar } from '../../utils/health'
import { formatBytes as fmtBytes, horaCurta } from '../../utils/format'

/**
 * Card "Informações do Servidor" — porte do <script> embutido no index.html.
 * Cores, limiares, textos e ordem das métricas idênticos ao original:
 * CPU · RAM · Disco · Temperatura · Latência · Uptime.
 */

function Barra({ pct, corPadrao, limiares }) {
  const cor = corPorLimiar(pct, corPadrao, limiares)
  return (
    <div className="sh-strip-bar-wrap">
      <div className="sh-strip-bar-track">
        <div
          className="sh-strip-bar-fill"
          style={{
            width: `${Math.min(pct, 100)}%`,
            background: cor,
            transition: 'width .6s ease, background .4s ease',
          }}
        />
      </div>
    </div>
  )
}

function Item({ cor, icone, rotulo, valor, valorCor, sub, children, valorPequeno }) {
  return (
    <div className="sh-strip-item">
      <div className="sh-strip-icon" style={{ color: cor }}>
        <i className={`bi ${icone}`} />
      </div>
      <div className="sh-strip-body">
        <span className="sh-strip-label">{rotulo}</span>
        <span
          className={`sh-strip-val${valorPequeno ? ' sh-strip-val-sm' : ''}`}
          style={valorCor ? { color: valorCor } : undefined}
        >
          {valor}
        </span>
        {children}
        {sub !== undefined && <span className="sh-strip-sub">{sub}</span>}
      </div>
    </div>
  )
}

export default function ServerHealthCard() {
  const { saude, badge, erro, atualizadoEm } = useServerHealth()

  const s = saude
  const cpuPct = s?.cpu_percentual ?? 0
  const ramPct = s?.ram?.percentual ?? 0
  const discoPct = s?.disco?.percentual ?? 0
  const temp = s?.temperatura_cpu
  const lat = s?.latencia_ms

  const temTemp = temp !== null && temp !== undefined
  const corTemp = !temTemp ? undefined : temp >= 85 ? '#ef4444' : temp >= 75 ? '#f59e0b' : '#10b981'
  const rotuloTemp = !temTemp ? 'N/D' : temp >= 85 ? 'Alta' : temp >= 75 ? 'Elevada' : 'Normal'

  const temLat = lat !== null && lat !== undefined
  const corLat = !temLat ? undefined : lat >= 150 ? '#ef4444' : lat >= 50 ? '#f59e0b' : '#10b981'
  const rotuloLat = !temLat
    ? 'N/D'
    : lat >= 150 ? 'Alta' : lat >= 50 ? 'Média' : lat < 10 ? 'Ótima' : 'Boa'

  return (
    <div className="card mb-4 border-0 shadow-sm" id="card-server-health">
      <div className="card-body py-3 px-4">
        <div className="sh-header mb-3">
          <div className="sh-header-top">
            <div className="server-health-icon">
              <i className="bi bi-hdd-network-fill" />
            </div>
            <div className="sh-header-titulo">
              <span className="fw-semibold text-dark" style={{ fontSize: '.9rem' }}>
                Servidor
              </span>
              <span className="text-muted ms-2" style={{ fontSize: '.75rem' }}>
                {window.location.host}
              </span>
            </div>
          </div>
          <div className="sh-header-meta">
            <span className={`badge ${badge.cls}`} style={{ fontSize: '.7rem' }}>
              <i
                className="bi bi-circle-fill me-1"
                style={{ fontSize: '.45rem', verticalAlign: 'middle' }}
              />
              {badge.texto}
            </span>
            <span className="text-muted" style={{ fontSize: '.7rem' }}>
              {atualizadoEm ? `Atualizado ${horaCurta(atualizadoEm)}` : '–'}
            </span>
          </div>
        </div>

        <div className="sh-strip">
          <Item cor="#3b82f6" icone="bi-cpu" rotulo="CPU" valor={s ? `${Math.round(cpuPct)}%` : '–'}>
            <Barra pct={cpuPct} corPadrao="#3b82f6" limiares={[[70, '#f59e0b'], [90, '#ef4444']]} />
          </Item>

          <div className="sh-strip-sep" />

          <Item
            cor="#8b5cf6" icone="bi-memory" rotulo="RAM"
            valor={s ? `${Math.round(ramPct)}%` : '–'}
            sub={s ? fmtBytes(s.ram.usado_gb, s.ram.total_gb) : '–'}
          >
            <Barra pct={ramPct} corPadrao="#8b5cf6" limiares={[[70, '#f59e0b'], [90, '#ef4444']]} />
          </Item>

          <div className="sh-strip-sep" />

          <Item
            cor="#f59e0b" icone="bi-device-hdd" rotulo="Disco"
            valor={s ? `${Math.round(discoPct)}%` : '–'}
            sub={s ? fmtBytes(s.disco.usado_gb, s.disco.total_gb) : '–'}
          >
            <Barra pct={discoPct} corPadrao="#f59e0b" limiares={[[70, '#ef4444']]} />
          </Item>

          <div className="sh-strip-sep" />

          <Item
            cor="#ef4444" icone="bi-thermometer-half" rotulo="Temp."
            valor={temTemp ? `${Math.round(temp)}°C` : '–'}
            valorCor={corTemp} sub={rotuloTemp}
          />

          <div className="sh-strip-sep" />

          <Item
            cor="#06534d" icone="bi-wifi" rotulo="Latência"
            valor={temLat ? `${Math.round(lat)} ms` : '–'}
            valorCor={corLat} sub={rotuloLat}
          />

          <div className="sh-strip-sep" />

          <Item
            cor="#10b981" icone="bi-clock-history" rotulo="Uptime"
            valor={s?.uptime || '–'} valorPequeno
          />
        </div>

        {erro && (
          <div className="text-danger small mt-2">
            <i className="bi bi-exclamation-triangle-fill" /> <span>{erro}</span>
          </div>
        )}
      </div>
    </div>
  )
}
