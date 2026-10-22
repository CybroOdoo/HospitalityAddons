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
import logging
import os

from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """PROP-05: Create the availability materialized view, indexes,
    pg_notify trigger, and cron job after module installation.
    """
    _create_sql_objects(env)
    _ensure_cron(env)


def _create_sql_objects(env):
    sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'availability_mv.sql')
    try:
        with open(sql_path, 'r') as fh:
            sql = fh.read()
        env.cr.execute(sql)
        _logger.info('PROP-05: availability SQL objects created/updated.')
    except Exception:
        _logger.exception('PROP-05: failed to execute availability_mv.sql')
        raise


def _ensure_cron(env):
    """Create the cron job if it doesn't already exist."""
    existing = env.ref(
        'hospitality_property.ir_cron_refresh_availability',
        raise_if_not_found=False,
    )
    if existing:
        return

    env['ir.cron'].sudo().create({
        'name': 'Hospitality: Refresh Availability MV',
        'model_id': env['ir.model']._get('hospitality.property').id,
        'state': 'code',
        'code': 'model._cron_refresh_availability()',
        'interval_number': 5,
        'interval_type': 'minutes',
        'active': True,
        'user_id': env.ref('base.user_root').id,
    })
    _logger.info('PROP-05: availability cron created.')