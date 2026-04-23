import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps {
  min?: number;
  max?: number;
  step?: number;
  value?: number[];
  onValueChange?: (value: number[]) => void;
  className?: string;
  disabled?: boolean;
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, min = 0, max = 100, step = 1, value = [50], onValueChange, disabled, ...props }, ref) => (
    <input
      ref={ref}
      type="range"
      min={min}
      max={max}
      step={step}
      value={value[0]}
      disabled={disabled}
      onChange={(e) => onValueChange?.([Number(e.target.value)])}
      className={cn(
        "w-full h-2 rounded-lg appearance-none cursor-pointer",
        "bg-muted accent-primary",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
)
Slider.displayName = "Slider"

export { Slider }
