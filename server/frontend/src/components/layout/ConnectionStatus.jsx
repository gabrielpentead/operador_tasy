import { useOperadores } from '../../context/OperadoresContext'

/**
 * Reúne os dois indicadores globais que common.js criava por JS:
 *  - #server-offline-overlay (tela cheia quando o servidor cai)
 *  - #indicador-conexao (bolinha fixa no canto inferior esquerdo)
 *
 * Marcação, ids e estilos inline são os mesmos do original, para que o
 * style.css existente continue valendo sem ajuste.
 */
export default function ConnectionStatus() {
  const { conectado, servidorOffline } = useOperadores()

  return (
    <>
      <div
        id="server-offline-overlay"
        className={servidorOffline ? 'active' : ''}
      >
        <div className="offline-content">
          <div className="offline-icon"><i className="bi bi-wifi-off" /></div>
          <h3 className="offline-title">Servidor Indisponível</h3>
          <p className="offline-message">
            A conexão com o servidor foi perdida. Tentando reconectar...
          </p>
          <div className="spinner-border reconnect-spinner" role="status">
            <span className="visually-hidden">Reconectando...</span>
          </div>
        </div>
      </div>

      <div
        id="indicador-conexao"
        title={conectado ? 'Conectado ao servidor' : 'Desconectado do servidor'}
        style={{
          position: 'fixed', bottom: '20px', left: '20px', zIndex: 9999,
          borderRadius: '50%', width: '15px', height: '15px',
          transition: 'all 0.3s ease', boxShadow: '0 0 10px rgba(0,0,0,0.3)',
          backgroundColor: conectado ? '#4caf50' : '#f44336',
          animation: conectado ? 'pulse 2s infinite' : 'none',
        }}
      />
    </>
  )
}
