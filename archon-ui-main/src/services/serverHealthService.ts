import { credentialsService } from './credentialsService';

interface HealthCheckCallback {
  onDisconnected: () => void;
  onReconnected: () => void;
}

class ServerHealthService {
  private healthCheckInterval: number | null = null;
  private isConnected: boolean = true;
  private missedChecks: number = 0;
  private callbacks: HealthCheckCallback | null = null;

  // Settings
  private disconnectScreenEnabled: boolean = true;
  private disconnectScreenDelay: number = 10000; // 10 seconds
  private maxMissedChecks: number = 2; // Show disconnect after 2 missed checks (10 seconds max)
  private checkInterval: number = 5000; // Check every 5 seconds (reduced frequency for heavy operations)

  async loadSettings() {
    try {
      // Load disconnect screen settings from API
      const enabledRes = await credentialsService.getCredential('DISCONNECT_SCREEN_ENABLED').catch(() => ({ value: 'true' }));
      this.disconnectScreenEnabled = enabledRes.value === 'true';
    } catch (error) {
      // Failed to load disconnect screen settings
    }
  }

  /**
   * Get the proper health check URL to avoid Traefik routing conflicts
   */
  private getHealthUrl(): string {
    // In production (Traefik), use absolute URL to ensure proper routing
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return `${window.location.protocol}//${window.location.host}/api/health`;
    }
    
    // In development, use relative URL
    return '/api/health';
  }

  async checkHealth(): Promise<boolean> {
    try {
      // Construct absolute URL for health check to avoid Traefik routing conflicts
      const healthUrl = this.getHealthUrl();
      console.log('🏥 [Health] Checking server health at', healthUrl);
      
      const response = await fetch(healthUrl, {
        method: 'GET',
        signal: AbortSignal.timeout(10000), // 10 second timeout (increased for heavy operations)
        headers: {
          'Accept': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
      
      console.log('🏥 [Health] Response:', response.status, response.statusText);
      
      if (response.ok) {
        const data = await response.json();
        console.log('🏥 [Health] Health data:', data);
        // Accept healthy, online, or initializing (server is starting up)
        const isHealthy = data.status === 'healthy' || data.status === 'online' || data.status === 'initializing';
        console.log('🏥 [Health] Is healthy:', isHealthy);
        return isHealthy;
      }
      console.error('🏥 [Health] Response not OK:', response.status);
      return false;
    } catch (error) {
      console.error('🏥 [Health] Health check failed:', error);
      
      // For network errors on MCP page, try one more time with a shorter timeout
      if (window.location.pathname === '/mcp' && error instanceof TypeError) {
        console.log('🏥 [Health] Retrying health check on MCP page...');
        try {
          const retryResponse = await fetch(this.getHealthUrl(), {
            method: 'GET',
            signal: AbortSignal.timeout(5000), // Shorter timeout for retry
            headers: {
              'Accept': 'application/json',
              'Cache-Control': 'no-cache'
            }
          });
          
          if (retryResponse.ok) {
            const data = await retryResponse.json();
            const isHealthy = data.status === 'healthy' || data.status === 'online' || data.status === 'initializing';
            console.log('🏥 [Health] Retry successful:', isHealthy);
            return isHealthy;
          }
        } catch (retryError) {
          console.error('🏥 [Health] Retry also failed:', retryError);
        }
      }
      
      return false;
    }
  }

  startMonitoring(callbacks: HealthCheckCallback) {
    this.callbacks = callbacks;
    this.missedChecks = 0;
    this.isConnected = true;

    // Load settings first
    this.loadSettings();

    // Start HTTP health polling
    this.healthCheckInterval = window.setInterval(async () => {
      const isHealthy = await this.checkHealth();
      
      if (isHealthy) {
        // Server is healthy
        if (this.missedChecks > 0) {
          // Was disconnected, now reconnected
          this.missedChecks = 0;
          this.handleConnectionRestored();
        }
      } else {
        // Server is not responding
        this.missedChecks++;
        // Health check failed
        
        // After maxMissedChecks failures, trigger disconnect screen
        if (this.missedChecks >= this.maxMissedChecks && this.isConnected) {
          this.isConnected = false;
          if (this.disconnectScreenEnabled && this.callbacks) {
            // Triggering disconnect screen after multiple health check failures
            this.callbacks.onDisconnected();
          }
        }
      }
    }, this.checkInterval);

    // Do an immediate check
    this.checkHealth().then(isHealthy => {
      if (!isHealthy) {
        this.missedChecks = 1;
      }
    });
  }

  private handleConnectionRestored() {
    if (!this.isConnected) {
      this.isConnected = true;
      // Connection to server restored
      if (this.callbacks) {
        this.callbacks.onReconnected();
      }
    }
  }

  stopMonitoring() {
    if (this.healthCheckInterval) {
      window.clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    this.callbacks = null;
  }

  isServerConnected(): boolean {
    return this.isConnected;
  }

  /**
   * Immediately trigger disconnect screen without waiting for health checks
   * Used when WebSocket or other services detect immediate disconnection
   */
  handleImmediateDisconnect() {
    console.log('🏥 [Health] Immediate disconnect triggered');
    this.isConnected = false;
    this.missedChecks = this.maxMissedChecks; // Set to max to ensure disconnect screen shows
    
    if (this.disconnectScreenEnabled && this.callbacks) {
      console.log('🏥 [Health] Triggering disconnect screen immediately');
      this.callbacks.onDisconnected();
    }
  }

  /**
   * Handle when WebSocket reconnects - reset state but let health check confirm
   */
  handleWebSocketReconnect() {
    console.log('🏥 [Health] WebSocket reconnected, resetting missed checks');
    this.missedChecks = 0;
    // Don't immediately mark as connected - let health check confirm server is actually healthy
  }

  getSettings() {
    return {
      enabled: this.disconnectScreenEnabled,
      delay: this.disconnectScreenDelay
    };
  }

  async updateSettings(settings: { enabled?: boolean; delay?: number }) {
    if (settings.enabled !== undefined) {
      this.disconnectScreenEnabled = settings.enabled;
      await credentialsService.createCredential({
        key: 'DISCONNECT_SCREEN_ENABLED',
        value: settings.enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable disconnect screen when server is disconnected'
      });
    }
    
    if (settings.delay !== undefined) {
      this.disconnectScreenDelay = settings.delay;
      // You could save this to credentials as well if needed
    }
  }
}

export const serverHealthService = new ServerHealthService();