import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
    children: ReactNode
    /** Optional fallback UI. Receives error + reset function. */
    fallback?: (error: Error, reset: () => void) => ReactNode
}

interface ErrorBoundaryState {
    error: Error | null
}

/**
 * Catches rendering errors in child components so the rest of the app
 * keeps working. Wrap around any section that might receive bad data
 * (e.g. AI-generated content, API responses).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { error: null }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { error }
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('[ErrorBoundary]', error, info.componentStack)
    }

    reset = () => this.setState({ error: null })

    render() {
        if (this.state.error) {
            if (this.props.fallback) {
                return this.props.fallback(this.state.error, this.reset)
            }

            return (
                <div className="flex flex-col items-center justify-center gap-3 p-6 rounded-xl border border-red-200 bg-red-50 text-center">
                    <p className="text-sm font-medium text-red-700">
                        Something went wrong rendering this section.
                    </p>
                    <p className="text-xs text-red-500 max-w-md break-words">
                        {this.state.error.message}
                    </p>
                    <button
                        onClick={this.reset}
                        className="mt-1 px-4 py-1.5 text-xs font-medium rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                    >
                        Try Again
                    </button>
                </div>
            )
        }

        return this.props.children
    }
}
