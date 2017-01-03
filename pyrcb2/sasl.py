# Copyright (C) 2016 taylor.fish <contact@taylor.fish>
#
# This file is part of pyrcb2.
#
# pyrcb2 is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# As an additional permission under GNU GPL version 3 section 7, you may
# distribute non-source forms of comments (lines beginning with "#") and
# strings (text enclosed in quotation marks) in pyrcb2 source code without
# the copy of the GNU GPL normally required by section 4, provided you
# include a URL through which recipients can obtain a copy of the
# Corresponding Source and the GPL at no charge.
#
# pyrcb2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyrcb2.  If not, see <http://www.gnu.org/licenses/>.

from .messages import Message, Reply, Error, ANY, ANY_ARGS
from base64 import b64encode
from collections import OrderedDict

__all__ = ["SASL"]


class SASL:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger.getChild("sasl")
        self.handlers = OrderedDict(
            PLAIN=self.plain,
        )

    async def authenticate(self, account, password, mechanism, **kwargs):
        if account is not None:
            kwargs["account"] = account
        if password is not None:
            kwargs["password"] = password
        if mechanism not in self.handlers:
            raise ValueError(
                "Supported SASL mechanisms are: " +
                ", ".join(self.handlers.keys()),
            )

        if "sasl" not in self.bot.extensions:
            await self.enable_sasl()
        await self.start_authentication(mechanism)
        await self.handlers[mechanism](**kwargs)
        await self.complete_authentication()

    async def enable_sasl(self):
        result = await self.bot.cap_req("sasl")
        if not result.success:
            raise result.to_exception(
                "Could not enable IRCv3 'sasl' extension")

    async def start_authentication(self, mechanism):
        await self.bot.send_command("AUTHENTICATE", mechanism)
        result = await self.bot.wait_for(
            Message(ANY, "AUTHENTICATE", ANY),
            errors=[
                Error({
                    "ERR_SASLFAIL", "ERR_SASLTOOLONG", "ERR_SASLALREADY",
                    "RPL_SASLMECHS",
                }, ANY_ARGS),
                Error("ERR_UNKNOWNCOMMAND", "AUTHENTICATE", ANY),
            ],
        )

        if not result.success:
            raise result.to_exception("Could not begin authentication")

    async def complete_authentication(self):
        result = await self.bot.wait_for(
            Reply("RPL_SASLSUCCESS", ANY_ARGS),
            errors=Error({
                "ERR_NICKLOCKED", "ERR_SASLFAIL", "ERR_SASLTOOLONG",
                "ERR_SASLALREADY", "ERR_SASLABORTED",
            }, ANY_ARGS),
        )

        if not result.success:
            raise result.to_exception("Could not complete authentication")

    async def plain(self, account, password):
        auth_str = "{0}\0{0}\0{1}".format(account, password)
        auth_str = b64encode(auth_str.encode()).decode()
        await self.bot.send_command("AUTHENTICATE", auth_str)
