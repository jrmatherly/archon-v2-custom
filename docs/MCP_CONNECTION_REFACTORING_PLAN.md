# MCP Container Connection Refactoring Plan

## Overview

This document outlines the comprehensive refactoring plan to fix critical misconfigurations in the MCP (Model Context Protocol) container connections within the Archon V2 Alpha Custom project. The issues affect both Traefik-routed and direct connections between frontend, backend, and MCP services.

## 🔍 Issues Identified

### 1. Frontend Transport Type Inconsistencies

- **mcpClientService.ts**: Uses `"http"` transport type exclusively
- **mcpService.ts**: Defines different transport types (`"sse"`, `"stdio"`, `"docker"`, `"npx"`)
- **Backend**: Hardcoded to `"sse"` transport
- **Impact**: Frontend expects HTTP but backend only provides SSE

### 2. Environment Variable Mismatches

- **Frontend**: Uses `VITE_MCP_URL` (not set in docker-compose.yml)
- **Backend**: Uses `ARCHON_MCP_PORT=8051`
- **Fallback**: Frontend defaults to `"/mcp"` (relative path)
- **Impact**: Frontend has no proper MCP URL configuration

### 3. Docker Network Configuration Problems

- **archon-mcp**: Only on `aanai` network (proxy network commented out)
- **Traefik labels**: All commented out
- **Impact**: MCP service not accessible via Traefik

### 4. Connection URL Logic Conflicts

- **Frontend**: Builds URLs as `http://${host}:${port}/${transport}`
- **Backend**: Direct container communication via `archon-mcp:8051`
- **Impact**: Frontend tries localhost:8051 instead of proper routing

### 5. Server-Side vs Client-Side Connection Logic

- **Server-Side**: Container-to-container communication
- **Client-Side**: Browser connections need Traefik routing
- **Impact**: No distinction between internal and external connections

## 🛠️ Refactoring Implementation Plan

### Phase 1: Docker Configuration Updates

#### 1.1 Update docker-compose.yml - Frontend Environment

**File**: `docker-compose.yml`
**Section**: `frontend.environment`

```yaml
environment:
  - VITE_API_URL=http://${HOST:-localhost}:${ARCHON_SERVER_PORT:-8181}
  - VITE_MCP_URL=http://${HOST:-localhost}:${ARCHON_MCP_PORT:-8051}/mcp  # ADD THIS
  - ARCHON_SERVER_PORT=${ARCHON_SERVER_PORT:-8181}
  - HOST=${HOST:-localhost}
```

#### 1.2 Enable Traefik for MCP Service

**File**: `docker-compose.yml`
**Section**: `archon-mcp`

```yaml
archon-mcp:
  # ... existing config ...
  networks:
    - aanai
    - proxy  # UNCOMMENT THIS LINE
  labels:
    - "traefik.enable=true"  # UNCOMMENT AND UPDATE
    - "traefik.http.routers.archon-mcp-rtr.entrypoints=websecure"
    - "traefik.http.routers.archon-mcp-rtr.rule=Host(`aanai-archon.${DOMAIN_NAME}`) && PathPrefix(`/mcp`)"
    - "traefik.http.middlewares.mcp-stripprefix.stripprefix.prefixes=/mcp"
    - "traefik.http.routers.archon-mcp-rtr.middlewares=chain-no-auth@file,mcp-stripprefix"
    - "traefik.http.routers.archon-mcp-rtr.service=archon-mcp-svc"
    - "traefik.http.services.archon-mcp-svc.loadbalancer.server.port=${ARCHON_MCP_PORT:-8051}"
```

### Phase 2: Frontend Service Refactoring

#### 2.1 Standardize Transport Types

**Decision**: Use HTTP transport for frontend-to-MCP communication
**Rationale**: Browser-based connections work better with HTTP than SSE for MCP protocol

#### 2.2 Update mcpClientService.ts

**File**: `archon-ui-main/src/services/mcpClientService.ts`
**Lines**: 443-456

```typescript
async createArchonClient(): Promise<MCPClient> {
    const archonConfig: MCPClientConfig = {
        name: "Archon",
        transport_type: "http",
        connection_config: {
            // Use environment variable if set, otherwise fallback to development URL
            url: this.getMcpUrl(),
        },
        auto_connect: true,
        health_check_interval: 30,
        is_default: true,
    };
    
    // Add new method to determine MCP URL
    private getMcpUrl(): string {
        // Production/Docker environment
        if (import.meta.env.VITE_MCP_URL) {
            return import.meta.env.VITE_MCP_URL;
        }
        
        // Development environment
        if (import.meta.env.DEV) {
            return "http://localhost:8051/mcp";
        }
        
        // Fallback to relative path for Traefik routing
        return "/mcp";
    }
```

#### 2.3 Update mcpService.ts Configuration

**File**: `archon-ui-main/src/services/mcpService.ts`
**Lines**: 164-174

```typescript
async getConfiguration(): Promise<ServerConfig> {
    const response = await fetch(`${this.baseUrl}/api/mcp/config`);

    if (!response.ok) {
        // Return environment-aware default config
        return this.getDefaultConfig();
    }
    
    // ... existing code
}

private getDefaultConfig(): ServerConfig {
    // Use environment variable if available
    if (import.meta.env.VITE_MCP_URL) {
        const url = new URL(import.meta.env.VITE_MCP_URL);
        return {
            transport: "http",
            host: url.hostname,
            port: parseInt(url.port) || 8051,
        };
    }
    
    // Development fallback
    return {
        transport: "http",
        host: "localhost",
        port: 8051,
    };
}
```

#### 2.4 Update mcpServerService.ts URL Building

**File**: `archon-ui-main/src/services/mcpServerService.ts`
**Line**: 264

```typescript
// OLD: const mcpUrl = `http://${config.host}:${config.port}/${config.transport}`;
// NEW: Build URL based on transport type
const mcpUrl = this.buildMcpUrl(config);

private buildMcpUrl(config: ServerConfig): string {
    if (config.transport === "http") {
        // For HTTP transport, use the configured URL directly
        if (import.meta.env.VITE_MCP_URL) {
            return import.meta.env.VITE_MCP_URL;
        }
        return `http://${config.host}:${config.port}/mcp`;
    } else {
        // For SSE transport, use the original format
        return `http://${config.host}:${config.port}/${config.transport}`;
    }
}
```

### Phase 3: Backend Configuration Updates

#### 3.1 Add HTTP Transport Support (Optional)

**File**: `python/src/mcp/mcp_server.py`
**Consideration**: Evaluate if backend should support both SSE and HTTP transports

#### 3.2 Update Environment Variable Handling

**File**: `python/src/server/config/config.py`
**Ensure**: Proper handling of MCP service URLs for different environments

### Phase 4: Environment Configuration

#### 4.1 Create .env.example Updates

**File**: `.env.example`

```bash
# MCP Service Configuration
ARCHON_MCP_PORT=8051
VITE_MCP_URL=http://localhost:8051/mcp  # For development
# VITE_MCP_URL=https://aanai-archon.yourdomain.com/mcp  # For production with Traefik
```

#### 4.2 Update Development Documentation

**File**: `README.md` or `docs/DEVELOPMENT.md`

- Document new environment variables
- Explain MCP connection scenarios (dev vs production)
- Provide troubleshooting guide

### Phase 5: Testing & Validation

#### 5.1 Test Scenarios

1. **Local Development**: Direct connection to localhost:8051
2. **Docker Compose**: Container-to-container communication
3. **Traefik Routing**: Frontend → Traefik → MCP service
4. **Mixed Environment**: Some services behind Traefik, others direct

#### 5.2 Health Check Updates

**File**: `docker-compose.yml`
**Update**: MCP service health checks to verify both internal and external connectivity

```yaml
healthcheck:
  test: [
    "CMD", "sh", "-c",
    "python -c \"import socket; s=socket.socket(); s.connect(('localhost', ${ARCHON_MCP_PORT:-8051})); s.close()\" && curl -f http://localhost:${ARCHON_MCP_PORT:-8051}/health"
  ]
```

## 🎯 Implementation Priority

### High Priority (Critical for functionality)

1. ✅ Docker network configuration (add proxy network to archon-mcp)
2. ✅ Environment variable setup (VITE_MCP_URL)
3. ✅ Frontend URL resolution logic

### Medium Priority (Improves reliability)

1. ✅ Traefik label configuration
2. ✅ Transport type standardization
3. ✅ Health check improvements

### Low Priority (Nice to have)

1. ✅ Backend HTTP transport support
2. ✅ Enhanced error handling
3. ✅ Documentation updates

## 🔄 Rollback Plan

If issues arise during implementation:

1. **Revert docker-compose.yml changes**: Comment out proxy network and Traefik labels
2. **Restore original frontend logic**: Remove VITE_MCP_URL dependencies
3. **Use localhost fallback**: Ensure development environment still works

## 📋 Verification Checklist

- [ ] Frontend can connect to MCP in development (localhost:8051)
- [ ] Frontend can connect to MCP via Docker Compose (container networking)
- [ ] Frontend can connect to MCP via Traefik (production routing)
- [ ] Backend server-to-MCP communication still works
- [ ] Health checks pass for all scenarios
- [ ] Error handling works for connection failures
- [ ] Documentation reflects new configuration requirements

## 🚀 Next Steps

1. **Review and approve** this refactoring plan
2. **Create feature branch** for MCP connection fixes
3. **Implement changes** in phases as outlined above
4. **Test thoroughly** in all environments
5. **Update documentation** and deployment guides
6. **Merge to main** after validation

---

**Created**: 2025-08-07  
**Author**: Cascade AI Assistant  
**Status**: Ready for Implementation  
**Estimated Effort**: 4-6 hours
