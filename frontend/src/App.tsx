import { FormEvent, useState } from 'react';
import { QueryInterface } from './components/QueryInterface';
import { useAuth } from './context/AuthContext';
import { getApiErrorMessage } from './api';

export default function App() {
  const { isAuthenticated, isLoading, login, logout, username } = useAuth();
  const [loginUsername, setLoginUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(loginUsername, password);
      setPassword('');
    } catch (loginError) {
      setError(getApiErrorMessage(loginError, 'Login failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <main className="app-shell"><section className="panel">Checking saved session...</section></main>;
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">React + FastAPI</p>
        <h1>AI Ops Copilot</h1>
        <p className="hero-copy">
          Upload datasets, enforce access control, and ask operational questions through a polished React client backed by FastAPI.
        </p>
        <p className="hero-copy">
          The frontend is your primary demo surface. The backend remains required for authentication, uploads, storage, and AI orchestration.
        </p>
      </section>

      {isAuthenticated ? (
        <>
          <section className="panel account-panel">
            <div>
              <h2>Signed in</h2>
              <p>Authenticated as {username}.</p>
            </div>
            <button className="secondary-button" onClick={() => void logout()}>
              Log out
            </button>
          </section>
          <QueryInterface />
        </>
      ) : (
        <section className="panel">
          <h2>Sign in</h2>
          <p>Use a backend user account to retrieve accessible datasets and send questions.</p>
          <form className="form-grid" onSubmit={handleLogin}>
            <label className="field">
              <span>Username</span>
              <input value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </button>
            {error ? <p className="status error">{error}</p> : null}
          </form>
        </section>
      )}
    </main>
  );
}
