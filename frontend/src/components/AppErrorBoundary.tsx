import { Component, ReactNode } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  message: string | null;
};

export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { message: null };

  static getDerivedStateFromError(error: Error): State {
    return { message: error.message || "Unexpected UI error" };
  }

  render() {
    if (this.state.message) {
      return (
        <div className="app-fallback">
          <h1>Clearing Ledger</h1>
          <p>The screen could not load.</p>
          <pre>{this.state.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}
