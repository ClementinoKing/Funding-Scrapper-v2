import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";

import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

function Calendar({ className, classNames, showOutsideDays = true, ...props }) {
  return (
    <DayPicker
      captionLayout="dropdown"
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        root: "w-full ",
        month: "relative",
        // months: "flex flex-col",

        nav: "absolute top-3.5 right-3.5 p-1.5 flex items-center justify-center gap-2 z-10",
        nav_button: cn(
          buttonVariants({ variant: "outline" }),
          "h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100",
        ),
        // nav_button_previous: "absolute left-1",
        // nav_button_next: "absolute right-1",

        dropdowns: "flex gap-2 mb-2",
        // dropdown_root: "flex-1",
        dropdown: cn(
          buttonVariants({ variant: "outline" }),
          "w-full justify-between"
        ),

        // caption: "flex justify-center pt-1 relative items-center",
        caption_label: "hidden",

        table: "w-full border-collapse space-y-1",
        head_row: "flex",
        head_cell: "text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]",
        row: "flex w-full mt-2",
        cell: "h-9 w-9 text-center text-sm p-0 relative [&:has([aria-selected].day-range-end)]:rounded-r-md [&:has([aria-selected].day-outside)]:bg-accent/50 [&:has([aria-selected])]:bg-accent first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md focus-within:relative focus-within:z-20",
        
        day: cn(
          "h-9 w-9 text-center rounded-md p-0 font-normal hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground disabled:opacity-50 disabled:pointer-events-none",
          "aria-selected:bg-primary aria-selected:text-primary-foreground aria-selected:font-medium",
          "aria-selected:hover:bg-primary aria-selected:hover:text-primary-foreground",
          "aria-disabled:text-muted-foreground aria-disabled:pointer-events-none",
        ),
        day_button: cn(
          buttonVariants({ variant: "ghost" }),
          "border border-gray-200 dark:border-gray-700 cursor-pointer w-full h-full rounded-md leading-none flex items-center justify-center"
        ),
        day_today: "bg-accent text-accent-foreground",
        outside: "text-muted-foreground opacity-50",
        day_disabled: "text-muted-foreground opacity-50",
        day_range_middle: "aria-selected:bg-accent aria-selected:text-accent-foreground",
        day_range_end: "day-range-end",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{
        IconLeft: () => <ChevronLeft className="h-4 w-4" />,
        IconRight: () => <ChevronRight className="h-4 w-4" />,
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
