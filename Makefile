NAME= $(shell grep Name: *.spec | sed 's/^[^:]*:[^a-zA-Z]*//')
VERSION= $(shell grep Version: *.spec | sed 's/^[^:]*:[^0-9]*//')
RELEASE= $(shell grep Release: *.spec | cut -d"%" -f1 | sed 's/^[^:]*:[^0-9]*//')
build=$(shell pwd)/build
DATE=$(shell date "+%a, %d %b %Y %T %z")
dist=$(shell rpm --eval '%dist' | sed 's/%dist/.el5/')

default:
	@echo "Nothing to do"

install:
	@echo installing ...

dist:
	@mkdir -p  $(build)/$(NAME)-$(VERSION)/
	rsync -HaS --exclude ".git" --exclude "$(build)" * $(build)/$(NAME)-$(VERSION)/
	cd $(build); tar --gzip -cf $(NAME)-$(VERSION).tar.gz $(NAME)-$(VERSION)/; cd -

sources: dist
	cp $(build)/$(NAME)-$(VERSION).tar.gz .

prepare: dist
	@mkdir -p  $(build)/RPMS/noarch
	@mkdir -p  $(build)/SRPMS/
	@mkdir -p  $(build)/SPECS/
	@mkdir -p  $(build)/SOURCES/
	@mkdir -p  $(build)/BUILD/
	cp $(build)/$(NAME)-$(VERSION).tar.gz $(build)/SOURCES
	cp $(NAME).spec $(build)/SPECS

srpm: prepare
	rpmbuild -bs --define="dist ${dist}" --define='_topdir ${build}' $(build)/SPECS/$(NAME).spec

rpm: srpm
	rpmbuild --rebuild  --define='_topdir ${build}' --define="dist ${dist}" $(build)/SRPMS/$(NAME)-$(VERSION)-$(RELEASE)${dist}.src.rpm

clean:
	rm -f *~ $(NAME)-$(VERSION).tar.gz
	rm -rf $(build)

.PHONY: dist srpm rpm sources clean
