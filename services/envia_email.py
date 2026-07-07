import os
import smtplib
from email.message import EmailMessage


def enviar_email_verificacao(destinatario: str, codigo: str, nome: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_usuario = os.getenv("SMTP_USER")
    smtp_senha = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_usuario)

    mensagem = EmailMessage()
    mensagem["Subject"] = "Seu código de verificação do AdaptAI"
    mensagem["From"] = smtp_from
    mensagem["To"] = destinatario
    print('email enviado!')

    mensagem.set_content(
        f"""
Olá, {nome}!

Seu código de verificação do AdaptAI é:

{codigo}

Ele expira em 10 minutos.

Se você não tentou criar uma conta, ignore este email.
"""
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <body style="margin:0; padding:0; background-color:#f4f7fb; font-family:Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f7fb; padding:40px 0;">
            <tr>
                <td align="center">
                    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.08);">
                        
                        <tr>
                            <td style="background:linear-gradient(135deg, #4f46e5, #7c3aed); padding:28px; text-align:center;">
                                <h1 style="margin:0; color:#ffffff; font-size:28px;">
                                    AdaptAI
                                </h1>
                                <p style="margin:8px 0 0; color:#e0e7ff; font-size:15px;">
                                    Confirmação de cadastro
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:32px;">
                                <h2 style="margin:0 0 16px; color:#111827; font-size:22px;">
                                    Verifique seu email
                                </h2>

                                <p style="margin:0 0 20px; color:#4b5563; font-size:16px; line-height:1.5;">
                                    Olá, <span style="color:#4338ca">{nome}</span>! Use o código abaixo para ativar sua conta no AdaptAI.
                                </p>

                                <div style="background:#eef2ff; border:1px solid #c7d2fe; border-radius:12px; padding:20px; text-align:center; margin:28px 0;">
                                    <p style="margin:0 0 8px; color:#4338ca; font-size:14px; font-weight:bold;">
                                        Seu código de verificação
                                    </p>

                                    <div style="font-size:36px; letter-spacing:8px; font-weight:bold; color:#312e81;">
                                        {codigo}
                                    </div>
                                </div>

                                <p style="margin:0 0 16px; color:#6b7280; font-size:14px; line-height:1.5;">
                                    Esse código expira em <strong>10 minutos</strong>.
                                </p>

                                <p style="margin:0; color:#9ca3af; font-size:13px; line-height:1.5;">
                                    Se você não tentou criar uma conta no AdaptAI, pode ignorar este email com segurança.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="background:#f9fafb; padding:18px; text-align:center; color:#9ca3af; font-size:12px;">
                                © AdaptAI — Plataforma de estudos com inteligência artificial
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    mensagem.add_alternative(html, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port) as servidor:
        servidor.starttls()
        servidor.login(smtp_usuario, smtp_senha)
        servidor.send_message(mensagem)