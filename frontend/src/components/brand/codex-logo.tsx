import { cn } from "@/lib/utils";

export type CodexLogoProps = {
  className?: string;
  size?: number;
  alt?: string;
};

export function CodexLogo({ className, size = 32, alt = "" }: CodexLogoProps) {
  return (
    <img
      src="/brand/codex-ib-logo.png"
      alt={alt}
      width={size}
      height={size}
      className={cn("shrink-0 object-contain", className)}
      draggable={false}
      style={{ width: size, height: size }}
    />
  );
}
