import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent as BaseDialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const AlertDialog = Dialog;
const AlertDialogTrigger = DialogTrigger;
const AlertDialogHeader = DialogHeader;
const AlertDialogDescription = DialogDescription;
const AlertDialogTitle = DialogTitle;

type AlertDialogContentProps = React.ComponentPropsWithoutRef<typeof BaseDialogContent> & {
  size?: "default" | "sm";
};

const AlertDialogContent = React.forwardRef<
  React.ElementRef<typeof BaseDialogContent>,
  AlertDialogContentProps
>(({ className, size = "default", ...props }, ref) => (
  <BaseDialogContent
    ref={ref}
    className={cn(size === "sm" ? "max-w-md" : "max-w-xl", className)}
    {...props}
  />
));
AlertDialogContent.displayName = "AlertDialogContent";

const AlertDialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)} {...props} />;

const AlertDialogCancel = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof Button>
>(({ className, ...props }, ref) => (
  <DialogClose asChild>
    <Button ref={ref} variant="outline" className={className} {...props} />
  </DialogClose>
));
AlertDialogCancel.displayName = "AlertDialogCancel";

const AlertDialogAction = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof Button>
>(({ className, ...props }, ref) => (
  <DialogClose asChild>
    <Button ref={ref} className={cn("bg-destructive text-destructive-foreground hover:bg-destructive/90", className)} {...props} />
  </DialogClose>
));
AlertDialogAction.displayName = "AlertDialogAction";

export {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTrigger,
  AlertDialogTitle
};
