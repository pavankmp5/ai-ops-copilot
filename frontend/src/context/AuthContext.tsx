import { createContext, useContext, ReactNode, useEffect, useState } from 'react';
import api from '../api';

interface AuthContextType {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [accessToken, setAccessToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [refreshToken, setRefreshToken] = useState<string | null>(localStorage.getItem('refresh_token'));
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      try {
        const { data } = await api.get('/auth/me');
        const resolvedUsername = data.username ?? null;
        setUsername(resolvedUsername);
        if (resolvedUsername) {
          localStorage.setItem('username', resolvedUsername);
        }
      } catch (error) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        setAccessToken(null);
        setRefreshToken(null);
        setUsername(null);
      } finally {
        setIsLoading(false);
      }
    };

    void restoreSession();
  }, [accessToken]);

  const login = async (usernameValue: string, password: string) => {
    const body = new URLSearchParams();
    body.set('username', usernameValue);
    body.set('password', password);

    const { data } = await api.post('/auth/token', body, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    const nextAccessToken = data.tokens.access_token as string;
    const nextRefreshToken = data.tokens.refresh_token as string;
    const nextUsername = data.user.username as string;

    localStorage.setItem('access_token', nextAccessToken);
    localStorage.setItem('refresh_token', nextRefreshToken);
    localStorage.setItem('username', nextUsername);
    setAccessToken(nextAccessToken);
    setRefreshToken(nextRefreshToken);
    setUsername(nextUsername);
  };

  const logout = async () => {
    const storedRefreshToken = refreshToken ?? localStorage.getItem('refresh_token');

    try {
      if (storedRefreshToken) {
        await api.post('/auth/logout', { refresh_token: storedRefreshToken });
      }
    } catch (error) {
      console.warn('Logout request failed; clearing local session anyway.', error);
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('username');
      setAccessToken(null);
      setRefreshToken(null);
      setUsername(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        accessToken,
        refreshToken,
        username,
        isAuthenticated: Boolean(accessToken),
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
