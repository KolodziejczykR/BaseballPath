import { forwardRef } from "react"
import { clsx } from "clsx"

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, ...props }, ref) => {
    return (
      <div className="w-full">
        <input
          type={type}
          className={clsx(
            "flex h-12 w-full rounded-lg border bg-white px-4 py-3 text-base text-gray-900 transition-colors duration-200 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50",
            error
              ? "border-red-300 focus:border-red-500 focus:ring-red-500"
              : "border-gray-300 focus:border-blue-500 focus:ring-blue-500",
            className
          )}
          style={{
            WebkitBoxShadow: '0 0 0 1000px var(--autofill-bg, rgba(255, 255, 255, 0.1)) inset',
            WebkitTextFillColor: 'var(--autofill-text, inherit)',
            ...props.style
          }}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="mt-1 text-sm text-red-600">{error}</p>
        )}
      </div>
    )
  }
)

Input.displayName = "Input"

export { Input }