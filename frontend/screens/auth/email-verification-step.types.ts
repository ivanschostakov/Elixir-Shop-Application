export type EmailVerificationStepProps = {
    email: string
    isChecking: boolean
    isResending: boolean
    onEditEmail: () => void
    onResend: () => Promise<void>
    onVerify: (code: string) => Promise<boolean>
    statusMessage?: string
}
