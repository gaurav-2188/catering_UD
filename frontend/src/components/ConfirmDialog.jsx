import React from "react";
import { Dialog, DialogContent } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { AlertTriangle } from "lucide-react";

/**
 * A simple "Are you sure?" dialog used for destructive / state-changing actions.
 *
 * Usage: control with `open`, pass `title`, `description`, `confirmLabel`, `tone` ("danger"|"primary"),
 * and `onConfirm`. Clicking outside or pressing Esc cancels.
 */
export default function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", tone = "primary", onConfirm }) {
  const toneCls = tone === "danger"
    ? "bg-[#B33A3A] hover:bg-[#9A3030] text-white"
    : "bg-[#4A5D23] hover:bg-[#3C4B1C] text-white";
  const iconCls = tone === "danger" ? "bg-[#FDF3F3] border-[#EAB8B8] text-[#B33A3A]" : "bg-[#F2F4EC] border-[#C8D2A8] text-[#4A5D23]";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-2xl" data-testid="confirm-dialog">
        <div className="text-center p-2">
          <div className={`mx-auto h-14 w-14 rounded-2xl border flex items-center justify-center mb-4 ${iconCls}`}>
            <AlertTriangle className="h-7 w-7" />
          </div>
          <h3 className="font-display text-xl font-semibold mb-2" data-testid="confirm-title">{title}</h3>
          <p className="text-base text-[#5C6056] mb-6">{description}</p>
          <div className="flex gap-2 justify-center">
            <Button data-testid="confirm-cancel" variant="outline" className="h-11 rounded-xl px-5" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button data-testid="confirm-ok" className={`h-11 rounded-xl px-5 ${toneCls}`} onClick={onConfirm}>{confirmLabel}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
