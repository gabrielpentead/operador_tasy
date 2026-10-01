import { useOperadores } from '../../context/OperadoresContext'

/**
 * Porte do toast "Ponto Offline" do <script> do index.html.
 * Mesmos estilos inline, mesma animação slideInToast, mesmo tempo de 8 s
 * (controlado no OperadoresContext, junto do timer de 30 s).
 *
 * O áudio de ping do original era um WAV base64 de silêncio — ou seja, não
 * produzia som algum. Foi mantido fora do porte por não ter efeito audível;
 * está registrado no relatório de migração.
 */
export default function OfflineToasts() {
  const { toastsOffline, fecharToastOffline } = useOperadores()

  return (
    <>
      <style>{`
        @keyframes slideInToast {
          from { opacity:0; transform:translateX(40px); }
          to   { opacity:1; transform:translateX(0); }
        }
      `}</style>

      <div
        id="toast-container"
        style={{
          position: 'fixed', bottom: '1.5rem', right: '1.5rem', zIndex: 9999,
          display: 'flex', flexDirection: 'column', gap: '.5rem',
          minWidth: '280px', maxWidth: '340px',
        }}
      >
        {toastsOffline.map((t) => (
          <div
            key={t.id}
            style={{
              background: '#1e293b', color: '#f1f5f9', borderRadius: '10px',
              padding: '.75rem 1rem', boxShadow: '0 4px 20px rgba(0,0,0,.35)',
              display: 'flex', alignItems: 'center', gap: '.75rem',
              animation: 'slideInToast .3s ease', fontSize: '.85rem',
            }}
          >
            <span
              style={{
                background: '#ef4444', borderRadius: '50%', width: 32, height: 32,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <i className="bi bi-wifi-off" style={{ color: '#fff', fontSize: '.9rem' }} />
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '.8rem', color: '#fca5a5' }}>
                Ponto Offline
              </div>
              <div style={{ color: '#cbd5e1' }}>{t.nome}</div>
            </div>
            <button
              onClick={() => fecharToastOffline(t.id)}
              style={{
                background: 'transparent', border: 'none', color: '#94a3b8',
                fontSize: '1.1rem', cursor: 'pointer', lineHeight: 1, padding: 0,
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </>
  )
}
