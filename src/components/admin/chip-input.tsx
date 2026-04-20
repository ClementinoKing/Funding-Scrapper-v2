import { useMemo, useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface ChipInputProps {
  label: string;
  description?: string;
  placeholder?: string;
  values: string[];
  onChange: (values: string[]) => void;
  suggestions?: string[];
  className?: string;
}

const normalize = (value: string): string => value.trim().replace(/\s+/g, " ");

export function ChipInput({
  label,
  description,
  placeholder,
  values,
  onChange,
  suggestions = [],
  className
}: ChipInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [selectedSuggestion, setSelectedSuggestion] = useState("");

  const normalizedValues = useMemo(() => values.map((value) => normalize(value).toLowerCase()), [values]);

  const addValue = (rawValue: string) => {
    const next = normalize(rawValue);
    if (!next) {
      return;
    }
    if (normalizedValues.includes(next.toLowerCase())) {
      return;
    }
    onChange([...values, next]);
  };

  const removeValue = (index: number) => {
    onChange(values.filter((_, currentIndex) => currentIndex !== index));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addValue(inputValue);
      setInputValue("");
      return;
    }
    if (event.key === "Backspace" && !inputValue && values.length > 0) {
      event.preventDefault();
      removeValue(values.length - 1);
    }
  };

  const filteredSuggestions = suggestions.filter((suggestion) => {
    const normalized = normalize(suggestion).toLowerCase();
    if (!normalized || normalizedValues.includes(normalized)) {
      return false;
    }
    if (!inputValue.trim()) {
      return true;
    }
    return normalized.includes(normalize(inputValue).toLowerCase());
  });

  return (
    <div className={cn("space-y-2", className)}>
      <Label>{label}</Label>
      <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
        <div className="flex flex-wrap gap-2">
          {values.length ? (
            values.map((value, index) => (
              <div
                key={`${value}-${index}`}
                className="inline-flex items-center gap-1 rounded-full border border-emerald-900/10 bg-background px-3 py-1 text-xs text-foreground shadow-sm"
              >
                <span className="max-w-[220px] truncate">{value}</span>
                <button
                  type="button"
                  onClick={() => removeValue(index)}
                  className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label={`Remove ${value}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No values added yet.</p>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto]">
          <Input
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
          />
          <Select
            value={selectedSuggestion}
            onValueChange={(value) => {
              setSelectedSuggestion(value);
              addValue(value);
              setSelectedSuggestion("");
              setInputValue("");
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose suggestion" />
            </SelectTrigger>
            <SelectContent>
              {filteredSuggestions.length ? (
                filteredSuggestions.map((suggestion) => (
                  <SelectItem key={suggestion} value={suggestion}>
                    {suggestion}
                  </SelectItem>
                ))
              ) : (
                <SelectItem value="__none__" disabled>
                  No suggestions
                </SelectItem>
              )}
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              addValue(inputValue);
              setInputValue("");
            }}
          >
            Add
          </Button>
        </div>

        {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      </div>
    </div>
  );
}
