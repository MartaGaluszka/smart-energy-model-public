export const environment = {
  production: true,
  // OCI + nip.io: IP publiczne z myślnikami, np. 130.61.12.34 → poniżej.
  // Po utworzeniu VM podmień na realny host (patrz deploy/oci/README.md).
  apiBaseUrl: 'https://YOUR_PUBLIC_IP_DASHED.nip.io',
};
