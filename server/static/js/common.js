/**
 * common.js - Funções comuns para todas as páginas
 */

// Variável para controlar o socket e polling interval
let socket;
let pollingInterval = null;
const POLLING_DELAY_OFFLINE = 10000; // Polling lento quando offline
const POLLING_DELAY_ONLINE = CONFIG ? CONFIG.intervaloAtualizacao : 30000;

try {
    if (typeof io === 'undefined') {
        throw new Error('Biblioteca Socket.IO não carregada.');
    }
    // Configuração de reconexão ajustada para evitar spam
    socket = io({
        reconnection: true,
        reconnectionDelay: 2000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
        timeout: 10000
    });
} catch (e) {
    console.error('Erro crítico ao inicializar Socket.IO:', e);
    alert('Erro crítico: Não foi possível carregar a biblioteca de comunicação (Socket.IO).');
}

// Status da conexão
let websocketConectado = false;
let estadoAnteriorConexao = false; // Para controlar notificações de conexão/desconexão

// Objeto para armazenar os dados dos operadores
let dadosOperadores = [];

// Configurações globais (devem ser definidas antes de carregar este arquivo ou terão valores padrão)
if (typeof CONFIG === 'undefined') {
    var CONFIG = {
        atualizacaoAutomatica: true,
        intervaloAtualizacao: 30000, // 30 segundos
        timeoutNotificacao: 5000,    // 5 segundos para todas as notificações
    };
}

// Inicialização quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando sistema...');
    
    // Adiciona o overlay de offline se não existir no HTML (fallback)
    if (!document.getElementById('server-offline-overlay')) {
        const overlay = document.createElement('div');
        overlay.id = 'server-offline-overlay';
        overlay.innerHTML = `
            <div class="offline-content">
                <div class="offline-icon"><i class="bi bi-wifi-off"></i></div>
                <h3 class="offline-title">Servidor Indisponível</h3>
                <p class="offline-message">A conexão com o servidor foi perdida. Tentando reconectar...</p>
                <div class="spinner-border reconnect-spinner" role="status">
                    <span class="visually-hidden">Reconectando...</span>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    // Configurar conexão WebSocket
    configurarWebSocket();
    
    // Iniciar atualizações automáticas (se online)
    iniciarPolling();
    
    // Verificar se existem notificações persistentes no localStorage
    verificarNotificacoesPersistentes();
    
    // Remover notificações antigas do LocalStorage
    limparNotificacoesAntigas();
    
    // Carregar configurações do servidor
    carregarConfiguracoesServidor();
    
    // Configurar eventos do formulário de configurações
    configurarFormularioConfiguracoes();
});

function setServerOffline(isOffline) {
    const overlay = document.getElementById('server-offline-overlay');
    if (overlay) {
        if (isOffline) {
            overlay.classList.add('active');
            // Pausa polling agressivo
            clearInterval(pollingInterval);
        } else {
            overlay.classList.remove('active');
            // Retoma polling normal
            iniciarPolling();
        }
    }
}

function iniciarPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    if (CONFIG.atualizacaoAutomatica) {
        pollingInterval = setInterval(atualizarDados, POLLING_DELAY_ONLINE);
    }
}

// Configurar eventos do WebSocket
function configurarWebSocket() {
    // Evento de conexão estabelecida
    socket.on('connect', function() {
        console.log('Conectado ao servidor WebSocket');
        
        websocketConectado = true;
        atualizarIndicadorConexao(true);
        atualizarStatusServidor(true);
        setServerOffline(false); // Remove overlay
        
        // Recarrega dados imediatamente ao voltar
        atualizarDados();
    });
    
    // Evento de desconexão
    socket.on('disconnect', function(reason) {
        console.log('Desconectado do servidor WebSocket:', reason);
        
        websocketConectado = false;
        atualizarIndicadorConexao(false);
        atualizarStatusServidor(false);
        
        // Mostra overlay se a desconexão não foi intencional
        if (reason !== 'io client disconnect') {
            setServerOffline(true);
        }
    });
    
    // Evento de erro na conexão
    socket.on('connect_error', function(error) {
        // Console.log suprimido para evitar spam
        // console.error('Erro na conexão WebSocket:', error);
        
        websocketConectado = false;
        atualizarIndicadorConexao(false);
        atualizarStatusServidor(false);
        setServerOffline(true);
    });
    
    // Evento de alteração de configuração do servidor
    socket.on('servidor_config_alterada', function(data) {
        console.log('Configurações do servidor alteradas:', data);
        mostrarNotificacao(`Configurações do servidor alteradas. Aguarde o reinício do servidor...`, 'warning', 0, true);
        setTimeout(() => {
            const currentPath = window.location.pathname;
            window.location.href = `http://${data.host}:${data.port}${currentPath}`;
        }, 5000);
    });
}

// Adicionar indicador visual de status da conexão
function atualizarIndicadorConexao(conectado) {
    let indicador = document.getElementById('indicador-conexao');
    
    // Criar o indicador se não existir
    if (!indicador) {
        indicador = document.createElement('div');
        indicador.id = 'indicador-conexao';
        indicador.style.position = 'fixed';
        indicador.style.bottom = '20px';
        indicador.style.left = '20px';
        indicador.style.zIndex = '9999';
        indicador.style.borderRadius = '50%';
        indicador.style.width = '15px';
        indicador.style.height = '15px';
        indicador.style.transition = 'all 0.3s ease';
        indicador.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
        document.body.appendChild(indicador);
    }
    
    if (conectado) {
        indicador.style.backgroundColor = '#4caf50';
        indicador.title = 'Conectado ao servidor';
        indicador.style.animation = 'pulse 2s infinite';
    } else {
        indicador.style.backgroundColor = '#f44336';
        indicador.title = 'Desconectado do servidor';
        indicador.style.animation = 'none';
    }
}

// Atualizar dados da página
function atualizarDados() {
    // Só atualiza se estiver conectado para evitar erros de rede
    if (websocketConectado && typeof carregarOperadores === 'function') {
        carregarOperadores();
    }
}

// Mostrar notificação na página
function mostrarNotificacao(mensagem, tipo = 'info', tempo = CONFIG.timeoutNotificacao, persistente = false) {
    // Verificar se o container de notificações existe
    let container = document.getElementById('notificacoes-container');
    
    // Criar container se não existir
    if (!container) {
        container = document.createElement('div');
        container.id = 'notificacoes-container';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '5000';
        document.body.appendChild(container);
    }
    
    // Garantir que o tipo seja válido
    if (!['info', 'success', 'warning', 'danger'].includes(tipo)) {
        tipo = 'info'; // Valor padrão seguro
    }
    
    // Garantir que o tempo seja válido
    if (typeof tempo !== 'number' || tempo <= 0) {
        tempo = CONFIG.timeoutNotificacao;
    }
    
    // Criar ID único para a notificação
    const id = 'notificacao-' + Date.now();
    
    // Definir ícone com base no tipo
    let icone = 'bi-info-circle';
    if (tipo === 'success') icone = 'bi-check-circle';
    if (tipo === 'warning') icone = 'bi-exclamation-triangle';
    if (tipo === 'danger') icone = 'bi-x-circle';
    
    // Criar botão de fechar personalizado para notificações persistentes
    const botaoFechar = persistente ? 
        `<button type="button" class="btn-close me-2 m-auto" onclick="fecharNotificacaoPersistente('${id}')" aria-label="Fechar"></button>` :
        `<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>`;
    
    // Criar elemento da notificação com animação melhorada
    const html = `
        <div id="${id}" class="toast align-items-center text-white bg-${tipo} fade" role="alert" aria-live="assertive" aria-atomic="true" data-persistente="${persistente}">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="${icone} me-2"></i> ${mensagem}
                </div>
                ${botaoFechar}
            </div>
        </div>
    `;
    
    // Adicionar ao container
    container.innerHTML += html;
    
    // Inicializar e mostrar a notificação
    const notificacaoElement = document.getElementById(id);
    
    // Configuração do toast
    const toastConfig = {
        animation: true,
        autohide: !persistente, // Não ocultar automaticamente se for persistente
        delay: persistente ? 0 : tempo
    };
    
    const toast = new bootstrap.Toast(notificacaoElement, toastConfig);
    toast.show();
    
    // Salvar notificação persistente no localStorage
    if (persistente) {
        salvarNotificacaoPersistente(id, mensagem, tipo);
    }
    
    // Remover após esconder (para todas as notificações)
    notificacaoElement.addEventListener('hidden.bs.toast', function() {
        // Remover elemento do DOM após animação
        setTimeout(() => {
            if (notificacaoElement && notificacaoElement.parentNode) {
                notificacaoElement.remove();
            }
        }, 300);
    });
    
    return id;
}

// Salvar notificação persistente no localStorage
function salvarNotificacaoPersistente(id, mensagem, tipo) {
    const notificacoesPersistentes = JSON.parse(localStorage.getItem('notificacoesPersistentes') || '{}');
    notificacoesPersistentes[id] = {
        mensagem,
        tipo,
        timestamp: Date.now()
    };
    localStorage.setItem('notificacoesPersistentes', JSON.stringify(notificacoesPersistentes));
}

// Fechar notificação persistente
function fecharNotificacaoPersistente(id) {
    const notificacaoElement = document.getElementById(id);
    if (notificacaoElement) {
        // Ocultar visualmente
        const toast = bootstrap.Toast.getInstance(notificacaoElement);
        if (toast) toast.hide();
        
        // Remover do DOM quando ocultar
        notificacaoElement.addEventListener('hidden.bs.toast', function() {
            notificacaoElement.remove();
        });
        
        // Remover do localStorage
        const notificacoesPersistentes = JSON.parse(localStorage.getItem('notificacoesPersistentes') || '{}');
        if (notificacoesPersistentes[id]) {
            delete notificacoesPersistentes[id];
            localStorage.setItem('notificacoesPersistentes', JSON.stringify(notificacoesPersistentes));
        }
    }
}

// Verificar e mostrar notificações persistentes do localStorage
function verificarNotificacoesPersistentes() {
    const notificacoesPersistentes = JSON.parse(localStorage.getItem('notificacoesPersistentes') || '{}');
    
    // Verificar se alguma notificação está desatualizada (mais de 24h)
    const agora = Date.now();
    const LIMITE_24H = 24 * 60 * 60 * 1000; // 24 horas em milissegundos
    
    Object.keys(notificacoesPersistentes).forEach(id => {
        const notificacao = notificacoesPersistentes[id];
        
        // Verificar se a notificação está desatualizada
        if (agora - notificacao.timestamp > LIMITE_24H) {
            delete notificacoesPersistentes[id];
        } else {
            // Mostrar notificação ainda válida
            mostrarNotificacao(notificacao.mensagem, notificacao.tipo, 0, true);
        }
    });
    
    // Atualizar localStorage se alguma notificação foi removida
    localStorage.setItem('notificacoesPersistentes', JSON.stringify(notificacoesPersistentes));
}

// Remover notificações antigas do localStorage (mais de 24h)
function limparNotificacoesAntigas() {
    const notificacoesPersistentes = JSON.parse(localStorage.getItem('notificacoesPersistentes') || '{}');
    let foiModificado = false;
    
    // Verificar notificações desatualizadas
    const agora = Date.now();
    const LIMITE_24H = 24 * 60 * 60 * 1000; // 24 horas em milissegundos
    
    Object.keys(notificacoesPersistentes).forEach(id => {
        const notificacao = notificacoesPersistentes[id];
        
        // Remover notificações antigas
        if (agora - notificacao.timestamp > LIMITE_24H) {
            delete notificacoesPersistentes[id];
            foiModificado = true;
        }
    });
    
    // Atualizar localStorage se necessário
    if (foiModificado) {
        localStorage.setItem('notificacoesPersistentes', JSON.stringify(notificacoesPersistentes));
    }
}

// Formatar data para exibição
function formatarData(dataString) {
    if (!dataString) return '-';
    
    try {
        const data = new Date(dataString);
        return data.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return dataString; // Retornar a string original em caso de erro
    }
}

// Formatar tempo relativo (há quanto tempo)
function tempoRelativo(dataString) {
    if (!dataString) return '';
    
    try {
        const data = new Date(dataString);
        const agora = new Date();
        
        const diff = Math.floor((agora - data) / 1000); // diferença em segundos
        
        if (diff < 30) return 'agora mesmo';
        if (diff < 60) return `há ${diff} segundos`;
        if (diff < 3600) {
            const minutos = Math.floor(diff / 60);
            return `há ${minutos} ${minutos === 1 ? 'minuto' : 'minutos'}`;
        }
        if (diff < 86400) {
            const horas = Math.floor(diff / 3600);
            return `há ${horas} ${horas === 1 ? 'hora' : 'horas'}`;
        }
        
        const dias = Math.floor(diff / 86400);
        return `há ${dias} ${dias === 1 ? 'dia' : 'dias'}`;
    } catch (e) {
        return '';
    }
}

// Escapa HTML para prevenir XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Carregar configurações do servidor
async function carregarConfiguracoesServidor() {
    if (!websocketConectado) return; // Não tenta se estiver offline
    try {
        const response = await fetch('/api/servidor/config');
        const data = await response.json();
        
        if (data.success) {
            const configIp = document.getElementById('config-ip');
            const configPorta = document.getElementById('config-porta');
            const serverIp = document.getElementById('server-ip');
            const serverPort = document.getElementById('server-port');
            
            if (configIp) configIp.value = data.config.host;
            if (configPorta) configPorta.value = data.config.port;
            if (serverIp) serverIp.textContent = data.config.host;
            if (serverPort) serverPort.textContent = data.config.port;
        }
    } catch (error) {
        console.error('Erro ao carregar configurações do servidor:', error);
    }
}

// Configurar o formulário de configurações
function configurarFormularioConfiguracoes() {
    const btnSalvarConfiguracoes = document.getElementById('btnSalvarConfiguracoes');
    
    if (btnSalvarConfiguracoes) {
        btnSalvarConfiguracoes.addEventListener('click', async function() {
            const configIp = document.getElementById('config-ip').value.trim();
            const configPorta = parseInt(document.getElementById('config-porta').value);
            
            if (!configIp || isNaN(configPorta) || configPorta < 1024 || configPorta > 65535) {
                mostrarNotificacao('Endereço IP ou porta inválidos', 'danger', 5000, false);
                return;
            }
            
            try {
                const response = await fetch('/api/servidor/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        host: configIp,
                        port: configPorta
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    mostrarNotificacao('Configurações do servidor atualizadas com sucesso!', 'success', 5000, false);
                    
                    // Fechar o modal
                    const modalConfiguracoes = bootstrap.Modal.getInstance(document.getElementById('modalConfiguracoes'));
                    if (modalConfiguracoes) {
                        modalConfiguracoes.hide();
                    }
                } else {
                    mostrarNotificacao(`Erro ao atualizar configurações: ${data.error}`, 'danger', 5000, false);
                }
            } catch (error) {
                console.error('Erro ao salvar configurações:', error);
                mostrarNotificacao('Erro de conexão ao atualizar configurações', 'danger', 5000, false);
            }
        });
    }
}

// Adicionar uma nova função para atualizar o status do servidor na interface
function atualizarStatusServidor(conectado) {
    const statusElement = document.getElementById('server-status');
    if (statusElement) {
        if (conectado) {
            statusElement.innerHTML = '<i class="bi bi-check-circle-fill"></i> Online';
            statusElement.className = 'badge status-badge online';
        } else {
            statusElement.innerHTML = '<i class="bi bi-x-circle-fill"></i> Offline';
            statusElement.className = 'badge status-badge offline';
        }
    }
}