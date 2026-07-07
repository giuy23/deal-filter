"""Arma el email digest con las ofertas top (SDD §6.2)."""
from __future__ import annotations

from datetime import datetime

from .models import Offer


def generate_digest_html(offers: list[Offer], recipient: str = "") -> str:
    """Genera HTML del email con las ofertas (top N)."""
    if not offers:
        return "<p>No hay ofertas nuevas esta vez.</p>"

    recipient_name = recipient.split("@")[0].capitalize() if recipient else "Usuario"

    rows = "\n".join(
        f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #ddd;">
                <a href="{o.url}" style="color: #0066cc; text-decoration: none; font-weight: 600;">
                    {o.title}
                </a>
                <br/>
                <span style="color: #666; font-size: 0.9em;">{o.company} • {o.remote}</span>
                <br/>
                <span style="color: #28a745; font-weight: bold;">Score: {o.score:.1f}</span>
                {' | '.join(o.stack[:3]) if o.stack else ''}
            </td>
        </tr>
        """
        for o in offers[:10]
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.5; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #0066cc; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            a {{ color: #0066cc; text-decoration: none; }}
            .footer {{ color: #666; font-size: 0.85em; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>JobDistiller — Resumen de ofertas</h1>
            <p>Hola {recipient_name},</p>
            <p>Aquí están las ofertas laborales más relevantes del último día:</p>

            <table>
                <thead>
                    <tr style="background-color: #f0f0f0;">
                        <th style="padding: 12px; text-align: left; font-weight: bold;">
                            Oferta
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>

            <p style="text-align: center;">
                <a href="https://jobdistiller.example.com"
                   style="background: #0066cc; color: white; padding: 10px 20px; border-radius: 4px; text-decoration: none;">
                    Ver todas las ofertas
                </a>
            </p>

            <div class="footer">
                <p>
                    Este email fue generado automáticamente por JobDistiller.<br>
                    Para desuscribirse o ajustar la frecuencia, edita tu configuración.
                </p>
                <p style="color: #ccc; font-size: 0.8em;">
                    Enviado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html
