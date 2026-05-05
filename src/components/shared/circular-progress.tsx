import { cn } from '@/lib/utils'

/**
 * Circular Progress Component
 * Displays a circular progress indicator with percentage text in the center
 * @param {number} value - Progress value (0-100)
 * @param {number} size - Size of the circle in pixels (default: 160)
 * @param {number} strokeWidth - Width of the stroke (default: 10)
 * @param {string} className - Additional CSS classes
 */
export function CircularProgress({ 
  value = 0, 
  size = 160, 
  strokeWidth = 10,
  className 
}: {
    value: number;
    size: number;
    strokeWidth: number;
    className?: string;
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference
  
  // Determine color based on score
  const getColor = (val) => {
    if (val >= 70) return 'text-green-600 dark:text-green-400'
    if (val >= 40) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }
  
  const getStrokeColor = (val) => {
    if (val >= 70) return 'stroke-green-600 dark:stroke-green-400'
    if (val >= 40) return 'stroke-yellow-600 dark:stroke-yellow-400'
    return 'stroke-red-600 dark:stroke-red-400'
  }

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
      >
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          className="text-muted opacity-20"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={getStrokeColor(value)}
          style={{
            transition: 'stroke-dashoffset 0.5s ease-in-out, stroke 0.3s ease-in-out'
          }}
        />
      </svg>
      {/* Percentage text */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <div className={cn("text-3xl font-bold", getColor(value))}>
            {Math.round(value)}%
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Match
          </div>
        </div>
      </div>
    </div>
  )
}
