# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HospitalityCommissionTier(models.Model):
    """Define commission rates based on partner volume tiers."""
    _name = 'hospitality.commission.tier'
    _description = 'Commission Tier'
    _order = 'partner_id, volume_basis, sequence, lower_volume'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        required=True,
        ondelete='cascade',
        index=True,
        help='Partner to whom this commission tier applies.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which commission tiers are evaluated or displayed.',
    )
    volume_basis = fields.Selection(
        selection=[
            ('nights',  'Nights'),
            ('revenue', 'Revenue'),
        ],
        string='Volume Basis',
        required=True,
        default='revenue',
        help='Metric used to determine the applicable commission tier.',
    )
    lower_volume = fields.Float(
        string='From (≥)',
        required=True,
        default=0.0,
        help='Minimum volume required for this commission tier.',
    )
    upper_volume = fields.Float(
        string='To (<)',
        default=0.0,
        help='Maximum volume for this tier; 0 means no upper limit.',
    )
    commission_pct = fields.Float(
        string='Commission %',
        required=True,
        digits=(10, 4),
        help='Commission percentage applied when this tier is applicable.',
    )

    @api.constrains('lower_volume', 'upper_volume', 'commission_pct')
    def _check_volumes(self):
        """Validate volume limits and commission percentage."""
        for rec in self:
            if rec.lower_volume < 0:
                raise ValidationError(
                    "Tier '%s': Lower Volume must be ≥ 0." % rec._description_display()
                )
            if rec.upper_volume and rec.upper_volume < rec.lower_volume:
                raise ValidationError(
                    "Tier '%s': Upper Volume must be ≥ Lower Volume (or 0 for open-ended)."
                    % rec._description_display()
                )
            if not (0 <= rec.commission_pct <= 100):
                raise ValidationError(
                    "Tier '%s': Commission %% must be between 0 and 100."
                    % rec._description_display()
                )

    @api.constrains('partner_id', 'volume_basis', 'lower_volume', 'upper_volume')
    def _check_no_overlap(self):
        """No two tiers for the same partner+volume_basis may overlap."""
        for rec in self:
            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('volume_basis', '=', rec.volume_basis),
                ('id', '!=', rec.id),
            ]
            others = self.search(domain)
            for other in others:
                if self._tiers_overlap(rec, other):
                    raise ValidationError(
                        "Commission tiers overlap for partner '%s' "
                        "(basis: %s, tier %s–%s conflicts with %s–%s)."
                        % (
                            rec.partner_id.name,
                            rec.volume_basis,
                            rec.lower_volume, rec.upper_volume or '∞',
                            other.lower_volume, other.upper_volume or '∞',
                        )
                    )

    @staticmethod
    def _tiers_overlap(a, b):
        """
        Return True when tier a and tier b cover an overlapping volume range.
        Open-ended: upper_volume == 0 means ∞
        Two ranges [a_lo, a_hi) and [b_lo, b_hi) overlap when a_lo < b_hi and b_lo < a_hi
        """
        a_upper = a.upper_volume if a.upper_volume else float('inf')
        b_upper = b.upper_volume if b.upper_volume else float('inf')
        return a.lower_volume < b_upper and b.lower_volume < a_upper

    def _description_display(self):
        """Return a readable description of the commission tier."""
        self.ensure_one()
        return "%s/%s %s–%s" % (
            self.partner_id.name,
            self.volume_basis,
            self.lower_volume,
            self.upper_volume or '∞',
        )
