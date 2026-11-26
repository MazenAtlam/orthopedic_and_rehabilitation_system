import axios from 'axios';
import { API_BASE_URL } from './env';
import { useAuthStore } from '../store/authStore';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

const AUTH_BYPASS_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const url = String(originalRequest?.url ?? '');
    const isAuthEndpoint = AUTH_BYPASS_PATHS.some((path) => url.includes(path));

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint
    ) {
      originalRequest._retry = true;
      try {
        const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {}, { withCredentials: true });
        const newAccessToken: string = res.data.access_token;
        if (res.data.user) {
          useAuthStore.getState().login(res.data.user, newAccessToken);
        } else {
          useAuthStore.getState().setAccessToken(newAccessToken);
        }
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch {
        useAuthStore.getState().logout();
      }
    }
    return Promise.reject(error);
  },
);

export function extractApiError(
  err: unknown,
  fallback = 'Request failed. Please try again.',
): string {
  if (axios.isAxiosError(err)) {
    const payload = err.response?.data?.error;
    if (payload) {
      if (Array.isArray(payload.details) && payload.details.length > 0) {
        return payload.details
          .map((item: { field?: string; message?: string }) =>
            item.field ? `${item.field}: ${item.message}` : item.message,
          )
          .join(' • ');
      }
      if (typeof payload.message === 'string' && payload.message.trim()) {
        return payload.message;
      }
    }
    if (typeof err.message === 'string' && err.message.trim()) {
      return err.message;
    }
  }
  if (err instanceof Error && err.message.trim()) {
    return err.message;
  }
  return fallback;
}
