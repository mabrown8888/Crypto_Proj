import io from 'socket.io-client';

class SocketService {
  constructor() {
    this.socket = null;
    this.connected = false;
  }

  connect() {
    if (this.socket) {
      return this.socket;
    }

    // Connect to backend on port 5001
    this.socket = io('http://localhost:5001', {
      transports: ['polling', 'websocket'],
      upgrade: true,
      timeout: 10000,
      forceNew: true
    });

    this.socket.on('connect', () => {
      console.log('✅ Connected to AI Trading Co-Pilot backend');
      this.connected = true;
    });

    this.socket.on('disconnect', () => {
      console.log('❌ Disconnected from backend');
      this.connected = false;
    });

    this.socket.on('connect_error', (error) => {
      console.log('🔴 Connection error:', error);
      this.connected = false;
    });

    return this.socket;
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.connected = false;
    }
  }

  emit(event, data) {
    if (this.socket && this.connected) {
      this.socket.emit(event, data);
    }
  }

  on(event, callback) {
    if (this.socket) {
      this.socket.on(event, callback);
    }
  }

  off(event, callback) {
    if (this.socket) {
      this.socket.off(event, callback);
    }
  }

  isConnected() {
    return this.connected && this.socket && this.socket.connected;
  }
}

const socketService = new SocketService();
export default socketService;