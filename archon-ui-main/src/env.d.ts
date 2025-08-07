/// <reference types="vite/client" />

interface ImportMetaEnv {
	readonly VITE_HOST: string;
	readonly VITE_PORT: string;
	readonly VITE_API_URL?: string;
	readonly VITE_MCP_URL?: string;
	readonly ARCHON_SERVER_PORT?: string;
	readonly ARCHON_MCP_PORT?: string;
	readonly ARCHON_AGENTS_PORT?: string;
	// Add other environment variables here as needed
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
