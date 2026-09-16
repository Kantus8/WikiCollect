export async function api<T>(path: string, body?: unknown): Promise<T> {
  const key = crypto.randomUUID();
  for (let attempt = 0; attempt < 2; attempt++) {
    let response: Response;
    try {
      response = await fetch("/api" + path, {
        method: body === undefined ? "GET" : "POST",
        credentials: "same-origin",
        headers:
          body === undefined
            ? {}
            : { "Content-Type": "application/json", "Idempotency-Key": key },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(20000),
      });
    } catch (e) {
      if (attempt === 0) continue;
      throw new Error(
        "Connexion au serveur interrompue. Votre collection reste enregistrée ; actualisez avant de réessayer.",
      );
    }
    const result = await response.json().catch(() => ({
      detail: "Le serveur a renvoyé une réponse inattendue.",
    }));
    if (!response.ok)
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Cette opération ne peut pas être effectuée.",
      );
    return result as T;
  }
  throw new Error("Connexion indisponible");
}
