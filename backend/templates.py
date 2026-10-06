"""
Professional Email Templates for Rangrag Archviz Studio.
Generates responsive visual HTML emails and clean plain-text alternatives,
highlighting 3D Rendering, Architectural Animation, Interior Visualization, 360° Views & VR.
"""

from typing import Dict, Any

def render_html_email(lead: Dict[str, Any], personalized_message: str, subject: str = "") -> str:
    firm_name = lead.get("firm_name", "your firm")
    contact_name = lead.get("contact_name") or "there"
    city = lead.get("city", "your city")
    category = lead.get("category", "Architecture & Interior Design")
    
    # Portfolio and profile links
    portfolio_url = "https://rangragstudio.myportfolio.com/"
    instagram_url = "https://www.instagram.com/rangrag_studio/"
    linkedin_url = "https://www.linkedin.com/in/raj-shekhada/"
    
    # Format message paragraphs
    paragraphs = personalized_message.strip().split("\n\n")
    formatted_paragraphs = "".join([f"<p style='margin: 0 0 16px 0; line-height: 1.6; color: #374151; font-size: 15px;'>{p.strip()}</p>" for p in paragraphs if p.strip()])

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f5f7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f5f7; padding: 32px 16px;">
    <tr>
      <td align="center">
        <!-- Main Email Container -->
        <table role="presentation" width="100%" max-width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color: #0f172a; padding: 32px 32px 28px 32px; border-bottom: 3px solid #f59e0b; text-align: left;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <div style="font-size: 20px; font-weight: 800; letter-spacing: 0.08em; color: #ffffff; text-transform: uppercase;">
                      RANGRAG <span style="color: #f59e0b;">ARCHVIZ</span> STUDIO
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; letter-spacing: 0.05em; margin-top: 4px; text-transform: uppercase;">
                      High-End Architectural CGI • V-Ray • Corona • D5
                    </div>
                  </td>
                  <td align="right" style="vertical-align: middle;">
                    <a href="{portfolio_url}" style="display: inline-block; background-color: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; color: #f59e0b; font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 6px; text-decoration: none; text-transform: uppercase; letter-spacing: 0.05em;">Portfolio</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Personalized Body -->
          <tr>
            <td style="padding: 32px 32px 20px 32px;">
              <div style="font-size: 16px; font-weight: 600; color: #111827; margin-bottom: 16px;">
                Hi {contact_name},
              </div>
              
              {formatted_paragraphs}

              <!-- Visual Highlight Matrix -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0 28px 0; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                <tr>
                  <td style="padding: 20px;">
                    <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-bottom: 14px;">
                      Core Visualization Capabilities for {firm_name}
                    </div>
                    
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td width="50%" style="vertical-align: top; padding-right: 10px; padding-bottom: 12px;">
                          <div style="font-size: 13px; font-weight: 600; color: #0f172a;">🏛️ Photorealistic 3D Renders</div>
                          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">V-Ray & Corona exterior elevations, materials & lighting.</div>
                        </td>
                        <td width="50%" style="vertical-align: top; padding-left: 10px; padding-bottom: 12px;">
                          <div style="font-size: 13px; font-weight: 600; color: #0f172a;">🛋️ Luxury Interior Visuals</div>
                          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Curated textures, bespoke lighting & realistic furniture styling.</div>
                        </td>
                      </tr>
                      <tr>
                        <td width="50%" style="vertical-align: top; padding-right: 10px;">
                          <div style="font-size: 13px; font-weight: 600; color: #0f172a;">🎬 Architectural Animations</div>
                          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Cinematic 4K walkthroughs, day-to-night transitions & D5 motion.</div>
                        </td>
                        <td width="50%" style="vertical-align: top; padding-left: 10px;">
                          <div style="font-size: 13px; font-weight: 600; color: #0f172a;">🌐 360° Panoramas & VR</div>
                          <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Immersive virtual tours for client presentations & approvals.</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Action Callout Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0;">
                <tr>
                  <td align="center">
                    <a href="{portfolio_url}" style="display: inline-block; background-color: #0f172a; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 26px; border-radius: 6px; box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);">
                      Explore Rangrag Studio Lookbook &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin: 20px 0 0 0; font-size: 14px; line-height: 1.5; color: #4b5563;">
                Would you be open to a quick 5-minute visual showcase or reviewing our lookbook for {firm_name}’s upcoming design presentations?
              </p>
            </td>
          </tr>

          <!-- Signature Section -->
          <tr>
            <td style="padding: 20px 32px 32px 32px; border-top: 1px solid #f1f5f9; background-color: #ffffff;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <div style="font-size: 15px; font-weight: 700; color: #0f172a;">Raj Shekhada</div>
                    <div style="font-size: 13px; color: #64748b; margin-top: 2px;">Founder & 3D Visualization Specialist</div>
                    <div style="font-size: 13px; font-weight: 600; color: #d97706; margin-top: 1px;">Rangrag Archviz Studio</div>
                    
                    <div style="margin-top: 10px; font-size: 12px; color: #4b5563;">
                      <a href="{portfolio_url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">Online Portfolio</a> &nbsp;•&nbsp; 
                      <a href="{instagram_url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">Instagram @rangrag_studio</a> &nbsp;•&nbsp; 
                      <a href="{linkedin_url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">LinkedIn</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Clean Unsubscribe / Compliance Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 16px 32px; text-align: center; border-top: 1px solid #e2e8f0;">
              <div style="font-size: 11px; color: #94a3b8; line-height: 1.4;">
                This note was sent to {lead.get('email')} as a direct peer collaboration inquiry. If this isn't relevant to your studio right now, simply reply "unsubscribe" and we will never message again.
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html_template

def render_plain_text_email(lead: Dict[str, Any], personalized_message: str) -> str:
    contact_name = lead.get("contact_name") or "there"
    firm_name = lead.get("firm_name", "your studio")
    portfolio_url = "https://rangragstudio.myportfolio.com/"
    instagram_url = "https://www.instagram.com/rangrag_studio/"
    linkedin_url = "https://www.linkedin.com/in/raj-shekhada/"

    return f"""Hi {contact_name},

{personalized_message}

Core Visualization Capabilities at Rangrag Archviz Studio:
• Photorealistic 3D Renders (Exterior & Interior via Chaos V-Ray, Corona, and D5 Render)
• Architectural Walkthrough Animations (Cinematic 4K daylight transitions)
• 360° Interactive Panoramas & VR Virtual Tours for client approvals

You can view our curated lookbook and recent projects here:
{portfolio_url}

Would you be open to a quick 5-minute visual showcase or reviewing our lookbook for {firm_name}’s upcoming design presentations?

Best regards,

Raj Shekhada
Founder & 3D Visualization Specialist
Rangrag Archviz Studio
Portfolio: {portfolio_url}
Instagram: {instagram_url}
LinkedIn: {linkedin_url}

(If this isn't relevant to your studio, just reply 'unsubscribe' and we won't reach out again.)
"""

def generate_default_personalized_body(lead: Dict[str, Any]) -> str:
    firm_name = lead.get("firm_name", "your firm")
    city = lead.get("city", "your city")
    category = lead.get("category", "architectural and interior design")
    
    city_mention = f" in {city}" if city and city.lower() not in ["your city", "nan", "null"] else ""

    return (
        f"I came across {firm_name}'s distinguished work{city_mention} and wanted to reach out peer-to-peer. "
        f"As 3D visualization artists specializing in V-Ray, Corona, and D5 rendering, we collaborate closely with design practices "
        f"to translate architectural concepts into striking photorealistic imagery that wins client approvals instantly.\n\n"
        f"We know how time-intensive in-house rendering cycles can become during busy project deadlines. Our team acts as a seamless extension "
        f"of your design studio—handling everything from high-resolution exterior elevations and luxury interior mood styling "
        f"to fluid cinematic video walkthroughs and 360° VR presentations, with fast turnaround times and frictionless revision rounds."
    )

def generate_default_followup_body(lead: Dict[str, Any]) -> str:
    firm_name = lead.get("firm_name", "your studio")
    contact_name = lead.get("contact_name") or "there"
    
    return (
        f"Hope you are having a productive week. Following up on my previous note regarding 3D architectural visualization support for {firm_name}.\n\n"
        f"We recently completed several luxury interior and exterior CGI packages with fast turnaround times for firms presenting to demanding clients. "
        f"I wanted to see if {firm_name} has any upcoming concept pitches or presentation deadlines where our 3D renders, walkthrough animations, or VR tours could be helpful."
    )
