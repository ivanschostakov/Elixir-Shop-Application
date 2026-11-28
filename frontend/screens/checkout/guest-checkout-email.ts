// Pass the buyer's recovery email to payment without putting it in a route URL.
let recoveryEmail = ""
export const getGuestCheckoutEmail = () => recoveryEmail
export const setGuestCheckoutEmail = (email: string) => { recoveryEmail = email.trim() }
