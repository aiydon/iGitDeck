import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

import { AlertIcon } from "./icons";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Keeps a render failure from blanking the whole dashboard. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("render failed", error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="panel error-panel">
        <AlertIcon size={22} />
        <div>
          <h2>页面渲染失败</h2>
          <p>{error.message || "发生了未预期的错误"}</p>
        </div>
        <button
          type="button"
          className="button secondary"
          onClick={() => window.location.reload()}
        >
          重新加载
        </button>
      </div>
    );
  }
}
