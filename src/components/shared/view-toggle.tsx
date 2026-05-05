import { Button } from '@/components/ui/button'
import { LayoutGrid, List, Grid3x3 } from 'lucide-react'
import { cn } from '@/lib/utils'

const views = [
  { value: 'grid', icon: LayoutGrid, label: 'Grid' },
  { value: 'list', icon: List, label: 'List' },
  { value: 'compact', icon: Grid3x3, label: 'Compact' },
]

export function ViewToggle({ value = 'grid', onValueChange, className }: {
    value: 'grid' | 'list' | 'compact';
    onValueChange: (value: 'grid' | 'list' | 'compact') => void;
    className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-1 border rounded-md p-1', className)}>
      {views.map((view) => {
        const Icon = view.icon
        return (
          <Button
            key={view.value}
            variant={value === view.value ? 'default' : 'ghost'}
            size="sm"
            className="h-8 px-3"
            onClick={() => onValueChange(view.value as 'grid' | 'list' | 'compact')}
            aria-label={`Switch to ${view.label} view`}
          >
            <Icon className="h-4 w-4" />
          </Button>
        )
      })}
    </div>
  )
}

