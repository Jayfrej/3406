/**
 * @file index.js
 * @description Main entry point - exports all modules for bundler-free use
 * @module js/index
 *
 * This file exports all modules and can be imported as a single script.
 * For ES Modules support, use <script type="module">.
 */

// Config
export { default as appState } from './config/state.js';
export * from './config/constants.js';

// Utils
export * from './utils/helpers.js';

// Services
export * from './services/api.js';
export { default as toast } from './services/toast.js';
export { default as modal } from './services/modal.js';
export { default as sseService } from './services/sse.js';

// Controllers
export { default as themeController } from './controllers/theme.js';
export { default as loading } from './controllers/loading.js';
export { default as navigation } from './controllers/navigation.js';

// Modules
export { default as accountsModule } from './modules/accounts.js';
export { default as copyTradingModule } from './modules/copyTrading.js';
export { default as settingsModule } from './modules/settings.js';
export { default as systemLogsModule } from './modules/systemLogs.js';
export { default as historyModule } from './modules/history.js';

// Main App
export { default as TradingBotUI } from './app-modular.js';
