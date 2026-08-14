import { Component, ReactNode } from 'react';

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <div className="card">
            <h3>出错了</h3>
            <p className="muted">{this.state.error.message}</p>
            <button className="btn" onClick={() => this.setState({ error: null })}>重试</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
