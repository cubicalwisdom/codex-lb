/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

interface Window {
  codexIbElectron?: {
    minimizeToTray: (options: { toTray: boolean }) => Promise<boolean>;
    setMinimizeToTrayEnabled?: (enabled: boolean) => Promise<boolean>;
    setStartWithWindowsEnabled?: (enabled: boolean) => Promise<boolean>;
  };
}
