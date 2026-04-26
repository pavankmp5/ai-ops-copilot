import axios from 'axios';
import { AxiosError } from 'axios';

const runtimeConfig = window.__APP_CONFIG__ ?? {};
const apiBaseUrl = runtimeConfig.API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const docsUrl = runtimeConfig.DOCS_URL ?? `${apiBaseUrl.replace(/\/$/, '')}/docs`;

export const api = axios.create({
  baseURL: apiBaseUrl,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
export const frontendRuntimeConfig = {
  apiBaseUrl,
  docsUrl,
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (detail && typeof detail === 'object') {
      if ('error' in detail && typeof detail.error === 'string') {
        return detail.error;
      }
      return JSON.stringify(detail);
    }

    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}
